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

    async def start(self) -> None:
        await self.tg.bind_auto_reply_handler(self._on_incoming_message)
        logger.info("Auto-reply handler started")

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

        normalized = (text or "").strip().lower()
        keywords = {kw.lower() for kw in settings.auto_reply_keywords}
        if not any(keyword in normalized for keyword in keywords):
            return

        await sleep_fixed(settings.auto_reply_delay)
        reply_text = "اهلا بك! كيف يمكنني مساعدتك؟"
        await self.tg.send_text(user_id, reply_text)
        await self.database.log_interaction(user_id, "sent", reply_text)
        await self.database.log_operation("send", "success", f"Auto-reply sent to {user_id}")
