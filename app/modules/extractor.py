from __future__ import annotations

import logging
from datetime import datetime

from app.clients.telegram_client import TelegramClientManager
from app.database import Database
from app.utils.delays import sleep_fixed


logger = logging.getLogger(__name__)


class ExtractorService:
    def __init__(self, tg: TelegramClientManager, database: Database, default_delay: float) -> None:
        self.tg = tg
        self.database = database
        self.default_delay = default_delay

    async def extract_from_group(self, group: str | int, per_user_delay: float | None = None) -> int:
        delay = self.default_delay if per_user_delay is None else max(0.0, per_user_delay)
        members = await self.tg.iter_group_members(group)
        count = 0

        for member in members:
            last_seen = member.get("last_seen")
            if isinstance(last_seen, datetime):
                normalized_last_seen = last_seen
            else:
                normalized_last_seen = None

            await self.database.upsert_user(
                user_id=int(member["user_id"]),
                username=member.get("username"),
                phone=member.get("phone"),
                last_seen=normalized_last_seen,
            )
            count += 1
            await sleep_fixed(delay)

        await self.database.log_operation("extract", "success", f"Extracted {count} users from {group}")
        logger.info("Extracted %d users from %s", count, group)
        return count

    async def extract_from_admin_channels(self, per_user_delay: float | None = None) -> dict[str, int]:
        channels = await self.tg.list_admin_channels()
        results: dict[str, int] = {}

        for channel in channels:
            key = str(channel)
            try:
                results[key] = await self.extract_from_group(channel, per_user_delay)
            except Exception as exc:
                await self.database.log_operation("extract", "failed", f"{channel}: {exc}")
                logger.exception("Failed extracting channel %s", channel)
                results[key] = 0

        return results

    async def import_recent_interactions(self, days: int = 30) -> int:
        rows = await self.tg.fetch_recent_dialog_interactions(days=days)
        imported = 0

        for row in rows:
            user_id = row.get("user_id")
            if user_id is None:
                continue
            await self.database.upsert_user(
                user_id=int(user_id),
                username=row.get("username"),
                phone=None,
                last_seen=row.get("date"),
            )
            await self.database.log_interaction(user_id=int(user_id), direction="received", message_text=row.get("text"))
            imported += 1

        await self.database.log_operation("extract", "success", f"Imported {imported} recent interactions")
        return imported

    async def contacts_by_interaction_window(self, days: int) -> list[dict[str, str | int | None]]:
        records = await self.database.get_recent_interacted_users(days)
        return [
            {
                "user_id": record.user_id,
                "username": record.username,
                "phone": record.phone,
                "last_interaction": record.last_interaction.isoformat() if record.last_interaction else None,
            }
            for record in records
        ]
