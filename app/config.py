from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
EXPORT_DIR = DATA_DIR / "exports"
BACKUP_DIR = DATA_DIR / "backups"
SESSIONS_DIR = DATA_DIR / "sessions"


# Load .env from project root.
load_dotenv(BASE_DIR / ".env")


DEFAULT_AUTO_REPLY_KEYWORDS = ["اهلاً", "هلا", "مرحبا", "السلام عليكم", "هاي"]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_delay_range(raw: str | None, default: Tuple[float, float]) -> Tuple[float, float]:
    if not raw:
        return default

    parts = [segment.strip() for segment in raw.split(",")]
    if len(parts) != 2:
        return default

    try:
        low = float(parts[0])
        high = float(parts[1])
    except ValueError:
        return default

    return (low, high) if low <= high else (high, low)


def _as_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []

    ids: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            continue
    return ids


def _database_url_from_env() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        return configured

    sqlite_path = DATA_DIR / "telegram_manager.db"
    return f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"


@dataclass(slots=True)
class Settings:
    api_id: int = field(default_factory=lambda: _as_int(os.getenv("API_ID"), 0))
    api_hash: str = field(default_factory=lambda: os.getenv("API_HASH", "").strip())
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    admin_ids: list[int] = field(default_factory=lambda: _as_admin_ids(os.getenv("ADMIN_IDS")))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", "").strip())

    database_url: str = field(default_factory=_database_url_from_env)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())

    default_delay: float = field(default_factory=lambda: _as_float(os.getenv("DEFAULT_DELAY"), 1.5))
    random_delay_range: Tuple[float, float] = field(
        default_factory=lambda: _as_delay_range(os.getenv("RANDOM_DELAY_RANGE"), (1.0, 3.0))
    )

    batch_enabled: bool = field(default_factory=lambda: _as_bool(os.getenv("BATCH_ENABLED"), True))
    batch_size: int = field(default_factory=lambda: _as_int(os.getenv("BATCH_SIZE"), 25))
    batch_delay: float = field(default_factory=lambda: _as_float(os.getenv("BATCH_DELAY"), 20.0))

    auto_reply_delay: float = field(default_factory=lambda: _as_float(os.getenv("AUTO_REPLY_DELAY"), 3.0))
    auto_reply_keywords: list[str] = field(
        default_factory=lambda: [kw.strip() for kw in os.getenv("AUTO_REPLY_KEYWORDS", "").split(",") if kw.strip()]
        or DEFAULT_AUTO_REPLY_KEYWORDS.copy()
    )

    rest_mode: bool = field(default_factory=lambda: _as_bool(os.getenv("REST_MODE"), False))
    preferred_session: str = field(default_factory=lambda: os.getenv("PREFERRED_SESSION", "default"))
    backup_hour_utc: int = field(default_factory=lambda: _as_int(os.getenv("BACKUP_HOUR_UTC"), 2))
    safe_max_adds_per_day: int = field(default_factory=lambda: _as_int(os.getenv("SAFE_MAX_ADDS_PER_DAY"), 25))

    def validate(self) -> None:
        if self.api_id <= 0:
            raise ValueError("API_ID is missing or invalid in .env")
        if not self.api_hash:
            raise ValueError("API_HASH is missing in .env")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is missing in .env")
        if not self.admin_ids:
            raise ValueError("ADMIN_IDS is missing in .env")


settings = Settings()
