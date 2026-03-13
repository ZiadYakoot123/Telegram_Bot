from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError, UserPrivacyRestrictedError
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from app.config import settings
from app.database import Database
from app.utils.delays import sleep_fixed


logger = logging.getLogger(__name__)


class TelegramClientManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.clients: dict[str, TelegramClient] = {}
        self.active_session: str | None = None

    async def start_session(self, session_name: str, session_path: Path) -> TelegramClient:
        if session_name in self.clients:
            self.active_session = session_name
            return self.clients[session_name]

        client = TelegramClient(str(session_path), settings.api_id, settings.api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning(
                "Session '%s' is not authorized yet. Run login flow manually once (Telethon sign-in).",
                session_name,
            )

        self.clients[session_name] = client
        self.active_session = session_name
        logger.info("Telethon session started: %s", session_name)
        return client

    async def stop_all(self) -> None:
        for name, client in list(self.clients.items()):
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Failed disconnecting session %s", name)
            finally:
                self.clients.pop(name, None)

    def get_active_client(self) -> TelegramClient:
        if not self.active_session or self.active_session not in self.clients:
            raise RuntimeError("No active Telegram session. Start a session first.")
        return self.clients[self.active_session]

    async def safe_call(self, op_name: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await fn()
        except FloodWaitError as exc:
            wait_for = int(exc.seconds) + 2
            logger.warning("Flood wait in %s: sleeping %s seconds", op_name, wait_for)
            await self.database.log_operation("flood_wait", "info", f"{op_name}: wait {wait_for}s")
            await sleep_fixed(wait_for)
            return await fn()
        except RPCError as exc:
            await self.database.log_operation("error", "failed", f"{op_name}: {exc}")
            logger.exception("Telegram RPC error in %s", op_name)
            raise

    async def iter_group_members(self, entity: str) -> list[dict[str, Any]]:
        client = self.get_active_client()

        async def _do() -> list[dict[str, Any]]:
            members: list[dict[str, Any]] = []
            async for user in client.iter_participants(entity):
                members.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "phone": user.phone,
                        "last_seen": user.status.was_online if hasattr(user.status, "was_online") else None,
                    }
                )
            return members

        return await self.safe_call("iter_group_members", _do)

    async def list_admin_channels(self) -> list[str | int]:
        client = self.get_active_client()

        async def _do() -> list[str | int]:
            channels: list[str | int] = []
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if not getattr(dialog, "is_channel", False):
                    continue

                is_admin = bool(getattr(entity, "creator", False) or getattr(entity, "admin_rights", None))
                if is_admin:
                    username = getattr(entity, "username", None)
                    channels.append(f"@{username}" if username else getattr(entity, "id", 0))
            return channels

        return await self.safe_call("list_admin_channels", _do)

    async def send_text(self, recipient: str | int, message: str) -> Any:
        client = self.get_active_client()
        return await self.safe_call("send_text", lambda: client.send_message(recipient, message))

    async def send_file(self, recipient: str | int, path: str, caption: str | None = None) -> Any:
        client = self.get_active_client()
        return await self.safe_call("send_file", lambda: client.send_file(recipient, path, caption=caption))

    async def resolve_user_by_phone(self, phone_number: str) -> int | None:
        client = self.get_active_client()

        async def _do() -> int | None:
            contact_id = abs(hash(phone_number)) % (10**10)
            contacts = [InputPhoneContact(client_id=contact_id, phone=phone_number, first_name="Temp", last_name="Contact")]
            response = await client(ImportContactsRequest(contacts))
            if not response.users:
                return None
            return response.users[0].id

        return await self.safe_call("resolve_user_by_phone", _do)

    async def add_member_to_group(self, group: str, user: str | int) -> bool:
        client = self.get_active_client()

        async def _do() -> bool:
            try:
                await client(InviteToChannelRequest(channel=group, users=[user]))
                return True
            except UserPrivacyRestrictedError:
                logger.warning("Cannot add user %s due to privacy restrictions", user)
                return False

        return await self.safe_call("add_member_to_group", _do)

    async def bind_auto_reply_handler(self, callback: Callable[[int, str], Awaitable[None]]) -> None:
        from telethon import events

        client = self.get_active_client()

        @client.on(events.NewMessage(incoming=True))
        async def _on_new_message(event: Any) -> None:
            sender = await event.get_sender()
            user_id = getattr(sender, "id", None)
            text = event.raw_text or ""
            if user_id is None:
                return
            await callback(user_id, text)

    async def bind_welcome_handler(self, callback: Callable[[int, list[int]], Awaitable[None]]) -> None:
        from telethon import events

        client = self.get_active_client()

        @client.on(events.ChatAction())
        async def _on_chat_action(event: Any) -> None:
            if not (getattr(event, "user_joined", False) or getattr(event, "user_added", False)):
                return

            chat_id = getattr(event, "chat_id", None)
            if chat_id is None:
                return

            user_ids: list[int] = []
            users = getattr(event, "users", None) or []
            for user in users:
                uid = getattr(user, "id", None)
                if uid is not None:
                    user_ids.append(int(uid))

            if not user_ids:
                single_user_id = getattr(event, "user_id", None)
                if single_user_id is not None:
                    user_ids.append(int(single_user_id))

            if not user_ids:
                return

            await callback(int(chat_id), user_ids)

    async def fetch_recent_dialog_interactions(self, days: int = 30) -> list[dict[str, Any]]:
        client = self.get_active_client()
        min_date = datetime.utcnow().timestamp() - (days * 86400)

        async def _do() -> list[dict[str, Any]]:
            interactions: list[dict[str, Any]] = []
            async for dialog in client.iter_dialogs(limit=200):
                if not getattr(dialog, "is_user", False):
                    continue
                msg = dialog.message
                if not msg:
                    continue
                if msg.date.timestamp() < min_date:
                    continue

                interactions.append(
                    {
                        "user_id": getattr(dialog.entity, "id", None),
                        "username": getattr(dialog.entity, "username", None),
                        "text": msg.message,
                        "date": msg.date,
                    }
                )
            return interactions

        return await self.safe_call("fetch_recent_dialog_interactions", _do)
