from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from sqlalchemy import select, update

from app.config import SESSIONS_DIR
from app.database import AccountSession, Database


logger = logging.getLogger(__name__)


class SessionsManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(SESSIONS_DIR, 0o700)
        except OSError:
            logger.debug("Could not enforce permissions on sessions directory", exc_info=True)

    @staticmethod
    def _sanitize_session_name(session_name: str) -> str:
        # Prevent path traversal and keep Telethon session names filesystem-safe.
        normalized = (session_name or "").strip().replace("/", "_").replace("\\", "_")
        normalized = re.sub(r"[^\w.-]", "_", normalized, flags=re.UNICODE)
        normalized = normalized.lstrip(".")
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized or "session"

    def session_file(self, session_name: str) -> Path:
        safe_name = self._sanitize_session_name(session_name)
        return SESSIONS_DIR / safe_name

    async def sync_from_disk(self) -> None:
        session_files = list(SESSIONS_DIR.glob("*.session"))
        for file in session_files:
            try:
                os.chmod(file, 0o600)
            except OSError:
                logger.debug("Could not enforce permissions on session file %s", file)
        names = [file.stem for file in session_files]

        async with self.database.session() as session:
            for name in names:
                session_path = str(self.session_file(name).as_posix())
                existing = await session.execute(select(AccountSession).where(AccountSession.name == name))
                row = existing.scalar_one_or_none()
                if row is None:
                    session.add(AccountSession(name=name, session_path=session_path, is_active=False))

        logger.info("Synced %d session(s) from disk", len(names))

    async def register_session(self, session_name: str) -> None:
        async with self.database.session() as session:
            existing = await session.execute(select(AccountSession).where(AccountSession.name == session_name))
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(
                    AccountSession(
                        name=session_name,
                        session_path=str(self.session_file(session_name).as_posix()),
                        is_active=False,
                    )
                )

    async def list_sessions(self) -> list[str]:
        async with self.database.session() as session:
            rows = await session.execute(select(AccountSession.name).order_by(AccountSession.name.asc()))
            return list(rows.scalars())

    async def set_active_session(self, session_name: str) -> None:
        async with self.database.session() as session:
            await session.execute(update(AccountSession).values(is_active=False))
            row = await session.execute(select(AccountSession).where(AccountSession.name == session_name))
            account = row.scalar_one_or_none()
            if account is None:
                account = AccountSession(
                    name=session_name,
                    session_path=str(self.session_file(session_name).as_posix()),
                    is_active=True,
                )
                session.add(account)
            else:
                account.is_active = True

    async def get_active_session(self) -> str | None:
        async with self.database.session() as session:
            row = await session.execute(select(AccountSession).where(AccountSession.is_active.is_(True)))
            account = row.scalar_one_or_none()
            return account.name if account else None
