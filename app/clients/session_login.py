from __future__ import annotations

import asyncio

from telethon import TelegramClient

from app.config import settings


async def login_session(session_name: str) -> None:
    session_path = f"data/sessions/{session_name}"
    client = TelegramClient(session_path, settings.api_id, settings.api_hash)
    await client.start()
    me = await client.get_me()
    print(f"Session '{session_name}' authorized as: {getattr(me, 'username', None) or me.id}")
    await client.disconnect()


if __name__ == "__main__":
    name = input("Enter session name (default): ").strip() or "default"
    asyncio.run(login_session(name))
