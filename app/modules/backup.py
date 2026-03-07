from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import BACKUP_DIR
from app.database import Database


logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self, database: Database) -> None:
        self.database = database
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _resolve_sqlite_path(self) -> Path | None:
        url = self.database.url
        if not url.startswith("sqlite+aiosqlite:///"):
            return None
        return Path(url.replace("sqlite+aiosqlite:///", "", 1))

    async def create_backup(self) -> Path | None:
        db_path = self._resolve_sqlite_path()
        if db_path is None:
            logger.info("Skipping file backup: non-sqlite database in use")
            await self.database.log_operation("backup", "info", "Skipped backup for non-sqlite database")
            return None

        if not db_path.exists():
            logger.warning("Database file not found for backup: %s", db_path)
            return None

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"db_backup_{stamp}.sqlite3"

        await asyncio.to_thread(shutil.copy2, db_path, backup_file)
        await self.database.log_operation("backup", "success", f"Created backup at {backup_file}")
        logger.info("Backup created at %s", backup_file)
        return backup_file
