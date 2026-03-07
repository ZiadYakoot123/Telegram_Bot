from __future__ import annotations

import logging
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from app.bot.keyboards import dashboard_keyboard, sessions_keyboard
from app.clients.sessions_manager import SessionsManager
from app.clients.telegram_client import TelegramClientManager
from app.database import Database
from app.modules.analytics import AnalyticsService
from app.modules.sender import MessagingService, SendPayload


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ControlBot:
    token: str
    admin_ids: list[int]
    admin_password: str
    database: Database
    sessions_manager: SessionsManager
    tg_manager: TelegramClientManager
    messaging: MessagingService
    analytics: AnalyticsService

    application: Application | None = None
    _password_authed_users: set[int] = field(default_factory=set)

    def _is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in set(self.admin_ids)

    def _is_fully_authorized(self, user_id: int | None) -> bool:
        if not self._is_admin(user_id):
            return False
        if not self.admin_password:
            return True
        return user_id in self._password_authed_users

    async def _require_auth(self, update: Update) -> bool:
        user_id = update.effective_user.id if update.effective_user else None
        if not self._is_admin(user_id):
            await update.effective_message.reply_text("Unauthorized")
            return False

        if self.admin_password and user_id not in self._password_authed_users:
            await update.effective_message.reply_text("Use /auth <password> first")
            return False

        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        rest_mode = (await self.database.get_setting("rest_mode", "0")) == "1"
        await update.message.reply_text("Control Panel", reply_markup=dashboard_keyboard(rest_mode))

    async def cmd_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id if update.effective_user else None
        if not self._is_admin(user_id):
            await update.message.reply_text("Unauthorized")
            return

        if not self.admin_password:
            await update.message.reply_text("Password auth is disabled")
            return

        if not context.args:
            await update.message.reply_text("Usage: /auth <password>")
            return

        if context.args[0] != self.admin_password:
            await update.message.reply_text("Invalid password")
            return

        self._password_authed_users.add(user_id)
        await update.message.reply_text("Authenticated successfully")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        stats = await self.analytics.get_basic_stats()
        top_words = await self.analytics.top_words(limit=10)
        words_text = "\n".join([f"- {word}: {count}" for word, count in top_words]) or "No words yet"

        text = (
            f"Sent: {stats['sent_messages']}\n"
            f"Received: {stats['received_messages']}\n"
            f"Known users: {stats['known_users']}\n\n"
            f"Top words:\n{words_text}"
        )
        await update.message.reply_text(text)

    async def cmd_template_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        raw = update.message.text.replace("/template_save", "", 1).strip()
        if "|" not in raw:
            await update.message.reply_text("Usage: /template_save name | content")
            return

        name, content = [part.strip() for part in raw.split("|", 1)]
        if not name or not content:
            await update.message.reply_text("Template name/content cannot be empty")
            return

        await self.database.save_template(name, content)
        await update.message.reply_text(f"Template '{name}' saved")

    async def cmd_template_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        raw = update.message.text.replace("/template_send", "", 1).strip()
        if len(raw.split()) < 2:
            await update.message.reply_text("Usage: /template_send <template_name> <@username>")
            return

        name, target = raw.split(maxsplit=1)
        template = await self.database.get_template(name)
        if template is None:
            await update.message.reply_text("Template not found")
            return

        await self.messaging.start()
        ok = await self.messaging.send_to_username(target, SendPayload(text=template.content, image_path=template.media_path))
        await update.message.reply_text("Template sent" if ok else "Template send failed")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id if query.from_user else None
        if not self._is_fully_authorized(user_id):
            await query.edit_message_text("Unauthorized")
            return

        data = query.data or ""

        if data == "send_start":
            await self.messaging.start()
            await query.edit_message_text("Sending mode started", reply_markup=dashboard_keyboard(await self._rest_mode()))
            return

        if data == "send_stop":
            await self.messaging.stop()
            await query.edit_message_text("Sending stopped", reply_markup=dashboard_keyboard(await self._rest_mode()))
            return

        if data == "rest_toggle":
            current = await self._rest_mode()
            await self.database.set_setting("rest_mode", "0" if current else "1")
            await query.edit_message_text(
                f"Rest mode {'enabled' if not current else 'disabled'}",
                reply_markup=dashboard_keyboard(not current),
            )
            return

        if data == "stats":
            stats = await self.analytics.get_basic_stats()
            await query.edit_message_text(
                f"Sent: {stats['sent_messages']} | Received: {stats['received_messages']} | Users: {stats['known_users']}",
                reply_markup=dashboard_keyboard(await self._rest_mode()),
            )
            return

        if data == "templates":
            templates = await self.database.list_templates()
            names = "\n".join([f"- {item.name}" for item in templates]) or "No templates saved"
            await query.edit_message_text(
                f"Templates:\n{names}",
                reply_markup=dashboard_keyboard(await self._rest_mode()),
            )
            return

        if data == "accounts":
            sessions = await self.sessions_manager.list_sessions()
            await query.edit_message_text("Select active session:", reply_markup=sessions_keyboard(sessions))
            return

        if data == "back_dashboard":
            await query.edit_message_text("Control Panel", reply_markup=dashboard_keyboard(await self._rest_mode()))
            return

        if data.startswith("switch_session:"):
            session_name = data.split(":", 1)[1]
            await self.sessions_manager.set_active_session(session_name)
            await self.tg_manager.start_session(session_name, self.sessions_manager.session_file(session_name))
            await query.edit_message_text(
                f"Active session switched to {session_name}",
                reply_markup=dashboard_keyboard(await self._rest_mode()),
            )
            return

    async def _rest_mode(self) -> bool:
        return (await self.database.get_setting("rest_mode", "0")) == "1"

    async def start(self) -> None:
        self.application = Application.builder().token(self.token).build()

        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("auth", self.cmd_auth))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("template_save", self.cmd_template_save))
        self.application.add_handler(CommandHandler("template_send", self.cmd_template_send))
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        await self.application.initialize()
        await self.application.start()

        if self.application.updater is None:
            raise RuntimeError("Telegram bot updater is unavailable")

        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Control bot polling started")

    async def shutdown(self) -> None:
        if self.application is None:
            return

        if self.application.updater is not None:
            await self.application.updater.stop()

        await self.application.stop()
        await self.application.shutdown()
        logger.info("Control bot stopped")
