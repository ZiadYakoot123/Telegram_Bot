from __future__ import annotations

import logging

from app.clients.telegram_client import TelegramClientManager
from app.config import settings
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

    async def _on_incoming_message(self, user_id: int, text: str) -> None:
        await self.database.log_interaction(user_id, "received", text)

        if not self.enabled:
            return
        if await self._is_rest_mode():
            return

        # Check if this user is in the allowed auto-reply list
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return

        # First check custom replies from database
        custom_reply = await self.database.get_custom_reply_by_keyword(text)
        if custom_reply:
            await self._sleep_reply_delay()
            
            # Send text reply
            if custom_reply.reply_text:
                reply_text = add_random_number_suffix(custom_reply.reply_text)
                reply_with_entropy = add_invisible_entropy(reply_text)
                await self.tg.send_text(user_id, reply_with_entropy)
            
            # Send media if available
            if custom_reply.media_path:
                try:
                    await self.tg.send_file(user_id, custom_reply.media_path)
                except Exception as exc:
                    logger.error(f"Failed to send media: {exc}")
            
            reply_log = custom_reply.reply_text or f"[Media: {custom_reply.media_type}]"
            await self.database.log_interaction(user_id, "sent", reply_log)
            await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
            return

        # Fallback to default keywords from settings if no custom reply found
        normalized = (text or "").strip().lower()
        keywords = {kw.lower() for kw in settings.auto_reply_keywords}
        if not any(keyword in normalized for keyword in keywords):
            return

        await self._sleep_reply_delay()
        reply_text = "اهلا بك! كيف يمكنني مساعدتك؟"
        reply_text = add_random_number_suffix(reply_text)
        reply_with_entropy = add_invisible_entropy(reply_text)
        await self.tg.send_text(user_id, reply_with_entropy)
        await self.database.log_interaction(user_id, "sent", reply_text)
        await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
