from __future__ import annotations

import logging
import random
from pathlib import Path

from app.clients.telegram_client import TelegramClientManager
from app.database import Database
from app.utils.helpers import add_invisible_entropy, add_random_number_suffix


logger = logging.getLogger(__name__)


class WelcomeService:
    def __init__(self, tg: TelegramClientManager, database: Database) -> None:
        self.tg = tg
        self.database = database

    async def start(self) -> None:
        await self.tg.bind_welcome_handler(self._on_members_joined)
        logger.info("Welcome handler started")

    async def _is_enabled(self) -> bool:
        value = await self.database.get_setting("welcome_enabled", "1")
        return (value or "1") == "1"

    async def _is_rest_mode(self) -> bool:
        value = await self.database.get_setting("rest_mode", "0")
        return (value or "0") == "1"

    async def _with_random_number(self) -> bool:
        value = await self.database.get_setting("welcome_random_number", "1")
        return (value or "1") == "1"

    async def _on_members_joined(self, chat_id: int, user_ids: list[int]) -> None:
        if not user_ids:
            return

        if not await self._is_enabled():
            return

        if await self._is_rest_mode():
            return

        messages = [msg for msg in await self.database.list_welcome_messages() if msg.enabled]
        if not messages:
            return

        selected = random.choice(messages)
        text = selected.content.strip()
        if not text and not selected.media_path:
            return

        media_path = selected.media_path
        if media_path:
            path = Path(media_path)
            if not path.exists():
                logger.warning("Welcome media not found: %s", media_path)
                media_path = None

        try:
            if media_path:
                welcome_text = selected.content.strip() if selected.content else None
                if welcome_text:
                    if await self._with_random_number():
                        welcome_text = add_random_number_suffix(welcome_text)
                    welcome_text = add_invisible_entropy(welcome_text)
                await self.tg.send_file(chat_id, media_path, caption=welcome_text or None)
            elif text:
                if await self._with_random_number():
                    text = add_random_number_suffix(text)
                text_with_entropy = add_invisible_entropy(text)
                await self.tg.send_text(chat_id, text_with_entropy)

            await self.database.log_operation(
                "welcome",
                "success",
                f"Welcome sent to chat={chat_id} joined={','.join(str(uid) for uid in user_ids)}",
            )
        except Exception as exc:
            await self.database.log_operation("welcome", "failed", f"chat={chat_id}: {exc}")
            logger.exception("Failed sending welcome to chat %s", chat_id)
