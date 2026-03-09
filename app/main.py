from __future__ import annotations

import asyncio
import logging
import signal

from app.bot.control_bot import ControlBot
from app.clients.sessions_manager import SessionsManager
from app.clients.telegram_client import TelegramClientManager
from app.config import settings
from app.database import db
from app.logger import setup_logging
from app.modules.analytics import AnalyticsService
from app.modules.auto_reply import AutoReplyService
from app.modules.backup import BackupService
from app.modules.batch_system import BatchConfig, BatchController
from app.modules.extractor import ExtractorService
from app.modules.scheduler import SchedulerService
from app.modules.sender import MessagingService


logger = logging.getLogger(__name__)


async def run() -> None:
    setup_logging()
    settings.validate()

    await db.init_models()
    await db.set_setting("rest_mode", "1" if settings.rest_mode else "0")

    sessions = SessionsManager(db)
    await sessions.sync_from_disk()
    await sessions.register_session(settings.preferred_session)

    active_session = await sessions.get_active_session()
    if active_session is None:
        active_session = settings.preferred_session
        await sessions.set_active_session(active_session)

    tg_manager = TelegramClientManager(db)
    await tg_manager.start_session(active_session, sessions.session_file(active_session))

    batch_controller = BatchController(
        BatchConfig(
            enabled=settings.batch_enabled,
            batch_size=settings.batch_size,
            delay_between_batches=settings.batch_delay,
        )
    )

    messaging = MessagingService(tg_manager, db, batch_controller)
    extractor = ExtractorService(tg_manager, db, settings.default_delay)
    analytics = AnalyticsService(db)
    scheduler = SchedulerService(db)
    backup = BackupService(db)
    auto_reply = AutoReplyService(tg_manager, db)

    scheduler.start()
    scheduler.scheduler.add_job(
        backup.create_backup,
        "cron",
        hour=settings.backup_hour_utc,
        minute=0,
        id="daily_backup",
        replace_existing=True,
    )

    await auto_reply.start()

    # Keep extractor referenced for future extension and scheduled jobs.
    _ = extractor

    control_bot = ControlBot(
        token=settings.bot_token,
        admin_ids=settings.admin_ids,
        admin_password=settings.admin_password,
        database=db,
        sessions_manager=sessions,
        tg_manager=tg_manager,
        messaging=messaging,
        extractor=extractor,
        analytics=analytics,
        auto_reply=auto_reply,
    )

    await control_bot.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except (NotImplementedError, RuntimeError):
            # Signal handlers are limited on Windows and some embedded runtimes.
            pass

    logger.info("Telegram manager is running")
    await stop_event.wait()

    logger.info("Shutdown requested")
    await control_bot.shutdown()
    await scheduler.shutdown()
    await tg_manager.stop_all()
    await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
