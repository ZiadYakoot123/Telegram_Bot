from __future__ import annotations

import logging
import random
from pathlib import Path

from app.clients.telegram_client import TelegramClientManager
from app.database import Database
from app.utils.delays import sleep_random
from app.utils.helpers import add_invisible_entropy, add_random_number_suffix


logger = logging.getLogger(__name__)


class AutoReplyService:
    def __init__(self, tg: TelegramClientManager, database: Database) -> None:
        self.tg = tg
        self.database = database
        self.enabled = True
        self.allowed_user_ids: set[int] = set()

    async def start(self) -> None:
        await self._load_allowed_users()
        await self.tg.bind_auto_reply_handler(self._on_incoming_message)
        logger.info("Auto-reply handler started")

    async def _load_allowed_users(self) -> None:
        """Load the list of users who are allowed to receive auto-replies"""
        user_ids = await self.database.get_enabled_auto_reply_user_ids()
        self.allowed_user_ids = set(user_ids)
        logger.info(f"Loaded {len(self.allowed_user_ids)} auto-reply users")

    async def reload_users(self) -> None:
        """Reload the list of allowed users (call after adding/removing users)"""
        await self._load_allowed_users()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    async def _is_rest_mode(self) -> bool:
        value = await self.database.get_setting("rest_mode", "0")
        return (value or "0") == "1"

    async def _sleep_reply_delay(self) -> None:
        default_low = 1.0
        default_high = 3.0

        raw_min = await self.database.get_setting("delay_min", str(default_low))
        raw_max = await self.database.get_setting("delay_max", str(default_high))

        try:
            low = max(0.0, float(raw_min if raw_min is not None else default_low))
        except (TypeError, ValueError):
            low = default_low

        try:
            high = max(0.0, float(raw_max if raw_max is not None else default_high))
        except (TypeError, ValueError):
            high = default_high

        if low > high:
            low, high = high, low

        await sleep_random(low, high)

    async def _on_incoming_message(self, chat_id: int, user_id: int, text: str, is_private: bool) -> None:
        await self.database.log_interaction(user_id, "received", text)

        if not self.enabled:
            return
        if await self._is_rest_mode():
            return
        # NOTE: Auto-reply currently targets everyone when enabled.
        # `allowed_user_ids` is kept for management visibility and future extensions.

        # First check custom replies from database
        custom_reply = await self.database.get_custom_reply_by_keyword(text)
        if custom_reply:
            await self._sleep_reply_delay()
            
            # Send text reply
            if custom_reply.reply_text:
                reply_text = add_random_number_suffix(custom_reply.reply_text)
                reply_with_entropy = add_invisible_entropy(reply_text)
                await self.tg.send_text(chat_id, reply_with_entropy)
            
            # Send media if available
            if custom_reply.media_path:
                try:
                    await self.tg.send_file(chat_id, custom_reply.media_path)
                except Exception as exc:
                    logger.error(f"Failed to send media: {exc}")
            
            reply_log = custom_reply.reply_text or f"[Media: {custom_reply.media_type}]"
            await self.database.log_interaction(user_id, "sent", reply_log)
            await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
            return

        # Send the generic welcome fallback only once per user (first message).
        if await self.database.has_welcome_once_sent(user_id, chat_id=chat_id):
            return

        # Fallback behavior: send a welcome reply for any incoming message.
        await self._sleep_reply_delay()

        welcome_messages = [msg for msg in await self.database.list_welcome_messages() if msg.enabled]
        if welcome_messages:
            selected = random.choice(welcome_messages)
            welcome_text = (selected.content or "").strip()
            media_path = selected.media_path

            if media_path:
                path = Path(media_path)
                if not path.exists():
                    logger.warning("Auto-reply welcome media not found: %s", media_path)
                    media_path = None

            if media_path:
                caption = None
                if welcome_text:
                    caption = add_invisible_entropy(add_random_number_suffix(welcome_text))
                await self.tg.send_file(chat_id, media_path, caption=caption)
                await self.database.log_interaction(user_id, "sent", welcome_text or "[welcome_media]")
                await self.database.log_operation(
                    "send",
                    "success",
                    f"Welcome auto-reply sent chat={chat_id} user={user_id} private={int(is_private)}",
                )
                await self.database.mark_welcome_once_sent(user_id, chat_id=chat_id)
                return

            if welcome_text:
                reply_with_entropy = add_invisible_entropy(add_random_number_suffix(welcome_text))
                await self.tg.send_text(chat_id, reply_with_entropy)
                await self.database.log_interaction(user_id, "sent", welcome_text)
                await self.database.log_operation(
                    "send",
                    "success",
                    f"Welcome auto-reply sent chat={chat_id} user={user_id} private={int(is_private)}",
                )
                await self.database.mark_welcome_once_sent(user_id, chat_id=chat_id)
                return

        # Final fallback when no configured welcome messages exist.
        reply_text = "اهلا بك! كيف يمكنني مساعدتك؟"
        reply_with_entropy = add_invisible_entropy(add_random_number_suffix(reply_text))
        await self.tg.send_text(chat_id, reply_with_entropy)
        await self.database.log_interaction(user_id, "sent", reply_text)
        await self.database.log_operation(
            "send",
            "success",
            f"Auto-reply sent chat={chat_id} user={user_id} private={int(is_private)}",
        )
        await self.database.mark_welcome_once_sent(user_id, chat_id=chat_id)
