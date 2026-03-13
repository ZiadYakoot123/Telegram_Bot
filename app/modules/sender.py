from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from app.clients.telegram_client import TelegramClientManager
from app.config import settings
from app.database import Database
from app.modules.batch_system import BatchController
from app.modules.filters import deduplicate_targets, filter_telegram_numbers_by_country
from app.utils.delays import sleep_random, sleep_with_jitter
from app.utils.helpers import add_invisible_entropy, add_random_number_suffix, random_hashtag
from app.utils.validators import is_valid_phone, is_valid_username


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SendPayload:
    text: str | None = None
    image_path: str | None = None
    file_path: str | None = None
    link: str | None = None
    random_hashtag_suffix: bool = False


class MessagingService:
    def __init__(self, tg: TelegramClientManager, database: Database, batch: BatchController) -> None:
        self.tg = tg
        self.database = database
        self.batch = batch
        self._is_running = False

    async def start(self) -> None:
        self._is_running = True
        self.batch.reset_stop()

    async def stop(self) -> None:
        self._is_running = False
        self.batch.emergency_stop()

    @property
    def is_running(self) -> bool:
        return self._is_running and not self.batch.is_stopped

    async def _is_rest_mode(self) -> bool:
        value = await self.database.get_setting("rest_mode", "0")
        return (value or "0") == "1"

    async def _runtime_delay_range(self) -> tuple[float, float]:
        default_low, default_high = settings.random_delay_range

        raw_min = await self.database.get_setting("delay_min", str(default_low))
        raw_max = await self.database.get_setting("delay_max", str(default_high))

        try:
            low = max(0.0, float(raw_min if raw_min is not None else default_low))
        except (TypeError, ValueError):
            low = max(0.0, float(default_low))

        try:
            high = max(0.0, float(raw_max if raw_max is not None else default_high))
        except (TypeError, ValueError):
            high = max(0.0, float(default_high))

        if low > high:
            low, high = high, low

        return low, high

    async def _sleep_runtime_delay(self) -> None:
        low, high = await self._runtime_delay_range()
        await sleep_random(low, high)

    def _compose_message(self, payload: SendPayload) -> str:
        parts: list[str] = []
        if payload.text:
            parts.append(payload.text)
        if payload.link:
            parts.append(payload.link)
        if payload.random_hashtag_suffix:
            parts.append(random_hashtag())
        text = "\n".join(parts).strip()
        text = add_random_number_suffix(text)
        # Add invisible entropy to prevent duplicate detection
        return add_invisible_entropy(text)

    async def _send_to_recipient(self, recipient_key: str, recipient: str | int, payload: SendPayload) -> bool:
        if await self._is_rest_mode():
            logger.info("Rest mode enabled; skipping recipient %s", recipient_key)
            await self.database.log_message(recipient_key, "text", "skipped", error="rest_mode")
            return False

        already_sent = await self.database.has_sent_to_recipient(recipient_key)
        if already_sent:
            logger.info("Skipping duplicate recipient: %s", recipient_key)
            await self.database.log_message(recipient_key, "text", "skipped", error="duplicate_prevented")
            return False

        body = self._compose_message(payload)

        try:
            if payload.image_path:
                await self.tg.send_file(recipient, payload.image_path, caption=body or None)
                msg_type = "image"
            elif payload.file_path:
                await self.tg.send_file(recipient, payload.file_path, caption=body or None)
                msg_type = "file"
            else:
                await self.tg.send_text(recipient, body)
                msg_type = "text"

            await self.database.log_message(recipient_key, msg_type, "sent")
            await self.database.log_interaction(None, "sent", body)
            await self.database.log_operation("send", "success", f"Sent to {recipient_key}")
            return True
        except Exception as exc:
            await self.database.log_message(recipient_key, "unknown", "failed", error=str(exc))
            await self.database.log_operation("send", "failed", f"{recipient_key}: {exc}")
            logger.exception("Failed to send to %s", recipient_key)
            return False

    async def send_to_username(self, username: str, payload: SendPayload) -> bool:
        if not is_valid_username(username):
            raise ValueError(f"Invalid username: {username}")
        normalized = username if username.startswith("@") else f"@{username}"
        return await self._send_to_recipient(f"username:{normalized.lower()}", normalized, payload)

    async def send_to_phone(self, phone_number: str, payload: SendPayload) -> bool:
        if not is_valid_phone(phone_number):
            raise ValueError(f"Invalid phone number: {phone_number}")

        user_id = await self.tg.resolve_user_by_phone(phone_number)
        if user_id is None:
            await self.database.log_operation("send", "failed", f"No Telegram account for {phone_number}")
            return False

        return await self._send_to_recipient(f"phone:{phone_number}", user_id, payload)

    async def send_bulk(self, targets: Iterable[str], payload: SendPayload, mode: str = "username") -> dict[str, int]:
        unique_targets = deduplicate_targets(list(targets))

        sent = 0
        failed = 0
        skipped = 0
        processed = 0

        for index, target in enumerate(unique_targets, start=1):
            if self.batch.is_stopped or not self._is_running:
                logger.warning("Bulk send interrupted due to stop signal")
                break

            if await self._is_rest_mode():
                logger.warning("Bulk send paused due to rest mode")
                break

            try:
                ok = (
                    await self.send_to_phone(target, payload)
                    if mode == "phone"
                    else await self.send_to_username(target, payload)
                )
                if ok:
                    sent += 1
                else:
                    skipped += 1
            except Exception:
                failed += 1

            processed += 1
            await self._sleep_runtime_delay()

            if self.batch.config.enabled and index % self.batch.config.batch_size == 0:
                await self.batch.wait_between_batches()

        return {"processed": processed, "sent": sent, "failed": failed, "skipped": skipped}

    async def check_numbers_on_telegram(self, phone_numbers: list[str]) -> dict[str, list[str]]:
        found: list[str] = []
        missing: list[str] = []

        for number in deduplicate_targets(phone_numbers):
            if not is_valid_phone(number):
                missing.append(number)
                continue

            user_id = await self.tg.resolve_user_by_phone(number)
            if user_id is None:
                missing.append(number)
            else:
                found.append(number)

            await self._sleep_runtime_delay()

        await self.database.log_operation(
            "extract",
            "success",
            f"Checked numbers: found={len(found)}, missing={len(missing)}",
        )
        return {"found": found, "missing": missing}

    async def filter_numbers_by_country(self, phone_numbers: list[str], country_codes: set[str]) -> list[str]:
        filtered = filter_telegram_numbers_by_country(phone_numbers, country_codes)
        await self.database.log_operation(
            "extract",
            "success",
            f"Country filter {country_codes}: kept={len(filtered)}/{len(phone_numbers)}",
        )
        return filtered

    async def add_members_gradually(
        self,
        group: str,
        users: list[str | int],
        max_per_day: int,
        delay_between_adds: float | None = None,
    ) -> dict[str, int]:
        added = 0
        failed = 0
        delay = settings.default_delay if delay_between_adds is None else max(0.0, delay_between_adds)
        safe_limit = min(max_per_day, settings.safe_max_adds_per_day)

        for user in users[:safe_limit]:
            if self.batch.is_stopped:
                break
            ok = await self.tg.add_member_to_group(group, user)
            if ok:
                added += 1
                await self.database.log_operation("add", "success", f"Added {user} to {group}")
            else:
                failed += 1
                await self.database.log_operation("add", "failed", f"Failed adding {user} to {group}")

            if delay_between_adds is None:
                await self._sleep_runtime_delay()
            else:
                await sleep_with_jitter(delay, (0.0, 0.0))

        return {"added": added, "failed": failed, "safe_limit": safe_limit}
