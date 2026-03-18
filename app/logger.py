from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from app.config import LOG_DIR, settings


_BOT_TOKEN_PATTERN = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _BOT_TOKEN_PATTERN.search(message):
            redacted = _BOT_TOKEN_PATTERN.sub("bot<redacted>", message)
            record.msg = redacted
            record.args = ()
        return True


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, settings.log_level, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        filename=LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce exposure of sensitive URLs (bot token can appear in request URLs at INFO level).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    secret_filter = RedactSecretsFilter()
    file_handler.addFilter(secret_filter)
    console_handler.addFilter(secret_filter)
