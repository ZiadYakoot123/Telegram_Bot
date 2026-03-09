from __future__ import annotations

import logging

from app.clients.telegram_client import TelegramClientManager
from app.config import settings
from app.database import Database
from app.utils.delays import sleep_fixed


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
            await sleep_fixed(settings.auto_reply_delay)
            
            # Send text reply
            await self.tg.send_text(user_id, custom_reply.reply_text)
            
            # Send media if available
            if custom_reply.media_path:
                try:
                    await self.tg.send_file(user_id, custom_reply.media_path)
                except Exception as exc:
                    logger.error(f"Failed to send media: {exc}")
            
            await self.database.log_interaction(user_id, "sent", custom_reply.reply_text)
            await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
            return

        # Fallback to default keywords from settings if no custom reply found
        normalized = (text or "").strip().lower()
        keywords = {kw.lower() for kw in settings.auto_reply_keywords}
        if not any(keyword in normalized for keyword in keywords):
            return

        await sleep_fixed(settings.auto_reply_delay)
        reply_text = "اهلا بك! كيف يمكنني مساعدتك؟"
        await self.tg.send_text(user_id, reply_text)
        await self.database.log_interaction(user_id, "sent", reply_text)
        await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
