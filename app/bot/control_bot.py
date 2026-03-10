from __future__ import annotations

import asyncio
import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.keyboards import (
    accounts_keyboard,
    auto_reply_keyboard,
    auto_reply_users_keyboard,
    bulk_keyboard,
    dashboard_keyboard,
    delay_keyboard,
    rest_keyboard,
    sessions_keyboard,
    stats_keyboard,
    welcome_keyboard,
    words_keyboard,
)
from app.clients.sessions_manager import SessionsManager
from app.clients.telegram_client import TelegramClientManager
from app.config import EXPORT_DIR
from app.database import Database
from app.modules.analytics import AnalyticsService
from app.modules.auto_reply import AutoReplyService
from app.modules.extractor import ExtractorService
from app.modules.sender import MessagingService, SendPayload


logger = logging.getLogger(__name__)


# Conversation states
WELCOME_ADD_TEXT, WELCOME_DELETE_ID = range(2)
AUTO_REPLY_ADD_KEYWORD, AUTO_REPLY_ADD_TEXT, AUTO_REPLY_DELETE_ID = range(3, 6)
AUTO_USER_ADD_ID, AUTO_USER_REMOVE_ID, AUTO_USER_TOGGLE_ID = range(6, 9)
DELAY_SET_MIN, DELAY_SET_MAX = range(9, 11)
BULK_TEXT_INPUT, BULK_TARGETS_INPUT = range(11, 13)


@dataclass(slots=True)
class ControlBot:
    token: str
    admin_ids: list[int]
    admin_password: str
    database: Database
    sessions_manager: SessionsManager
    tg_manager: TelegramClientManager
    messaging: MessagingService
    extractor: ExtractorService
    analytics: AnalyticsService
    auto_reply: AutoReplyService

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
            await update.effective_message.reply_text(
                f"Unauthorized. Your Telegram user ID is: {user_id}"
            )
            return False

        if self.admin_password and user_id not in self._password_authed_users:
            await update.effective_message.reply_text("Use /auth <password> first")
            return False

        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        await update.message.reply_text("لوحة التحكم الرئيسية", reply_markup=dashboard_keyboard())

    async def cmd_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id if update.effective_user else None
        if not self._is_admin(user_id):
            await update.message.reply_text(
                f"Unauthorized. Your Telegram user ID is: {user_id}"
            )
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
        ok = await self.messaging.send_to_username(
            target,
            SendPayload(text=template.content, image_path=template.media_path),
        )
        await update.message.reply_text("Template sent" if ok else "Template send failed")

    async def cmd_extract_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        if not context.args:
            await update.message.reply_text("Usage: /extract_group <group_id_or_username>")
            return

        group = context.args[0].strip()
        await update.message.reply_text(f"جاري استخراج المستخدمين من {group} ...")

        try:
            count = await self.extractor.extract_from_group(group)
            await update.message.reply_text(f"✅ تم استخراج {count} مستخدم من {group}")
        except Exception as exc:
            logger.exception("Failed to extract users from %s", group)
            await update.message.reply_text(f"❌ فشل الاستخراج: {exc}")

    async def cmd_extract_private(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return

        days = 30
        if context.args:
            try:
                days = int(context.args[0])
                if days <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Usage: /extract_private [days>0]")
                return

        await update.message.reply_text(f"جاري استخراج مستخدمي الخاص من آخر {days} يوم ...")

        try:
            imported = await self.extractor.import_recent_interactions(days=days)
            await update.message.reply_text(
                f"✅ تم استخراج {imported} مستخدم من الخاص (آخر {days} يوم)"
            )
        except Exception as exc:
            logger.exception("Failed to extract private interactions")
            await update.message.reply_text(f"❌ فشل استخراج الخاص: {exc}")

    async def _show_not_implemented(self, query, section: str, keyboard) -> None:
        await query.edit_message_text(
            f"{section}\n\nهذه الوظيفة ستحتاج خطوة إدخال إضافية.\n"
            "حالياً يمكنك استخدامها عبر الأوامر أو إعدادات .env.",
            reply_markup=keyboard,
        )

    async def _show_stats_overview(self, query) -> None:
        stats = await self.analytics.get_basic_stats()
        await query.edit_message_text(
            (
                "📊 الإحصائيات\n\n"
                f"عدد الرسائل المستلمة: {stats['received_messages']}\n"
                f"عدد الردود المرسلة: {stats['sent_messages']}\n"
                f"عدد المستخدمين: {stats['known_users']}"
            ),
            reply_markup=stats_keyboard(),
        )

    async def _show_top_words(self, query, title: str = "🔍 تحليل الكلمات") -> None:
        top_words = await self.analytics.top_words(limit=10)
        words_text = "\n".join([f"- {word}: {count}" for word, count in top_words]) or "لا توجد كلمات مسجلة حالياً"
        await query.edit_message_text(
            f"{title}\n\n{words_text}",
            reply_markup=words_keyboard(),
        )

    async def _export_top_words(self) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        top_words = await self.analytics.top_words(limit=2000)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = EXPORT_DIR / f"top_words_{timestamp}.csv"

        def _write() -> None:
            with out_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["word", "count"])
                for word, count in top_words:
                    writer.writerow([word, count])

        await asyncio.to_thread(_write)
        return str(out_path)

    async def _export_usernames(self) -> str:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        usernames = await self.database.list_usernames()

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = EXPORT_DIR / f"usernames_{timestamp}.csv"

        def _write() -> None:
            with out_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["username"])
                for username in usernames:
                    handle = username if username.startswith("@") else f"@{username}"
                    writer.writerow([handle])

        await asyncio.to_thread(_write)
        return str(out_path)

    # Welcome message conversation handlers
    async def welcome_add_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل نص رسالة الترحيب:\n\n"
            "مثال: مرحباً بك! سعيد بانضمامك 😊"
        )
        return WELCOME_ADD_TEXT

    async def welcome_add_text_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text
        await self.database.add_welcome_message(text)
        await update.message.reply_text(
            "✅ تم إضافة رسالة الترحيب بنجاح",
            reply_markup=welcome_keyboard(),
        )
        return ConversationHandler.END

    async def welcome_delete_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        messages = await self.database.list_welcome_messages()
        if not messages:
            await update.callback_query.message.reply_text(
                "لا توجد رسائل ترحيب لحذفها",
                reply_markup=welcome_keyboard(),
            )
            return ConversationHandler.END

        text = "اختر رقم الرسالة للحذف:\n\n"
        for msg in messages:
            preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            text += f"{msg.id}. {preview}\n"
        text += "\nأرسل رقم الرسالة:"

        await update.callback_query.message.reply_text(text)
        return WELCOME_DELETE_ID

    async def welcome_delete_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            msg_id = int(update.message.text.strip())
            deleted = await self.database.delete_welcome_message(msg_id)
            if deleted:
                await update.message.reply_text("✅ تم حذف الرسالة", reply_markup=welcome_keyboard())
            else:
                await update.message.reply_text("❌ الرسالة غير موجودة", reply_markup=welcome_keyboard())
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح", reply_markup=welcome_keyboard())
        return ConversationHandler.END

    # Auto reply conversation handlers
    async def auto_reply_add_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل الكلمة المفتاحية للرد التلقائي:\n\n"
            "مثال: السلام عليكم"
        )
        return AUTO_REPLY_ADD_KEYWORD

    async def auto_reply_add_keyword_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["auto_reply_keyword"] = update.message.text.strip()
        await update.message.reply_text(
            "أرسل نص الرد التلقائي:\n\n"
            "مثال: وعليكم السلام ورحمة الله"
        )
        return AUTO_REPLY_ADD_TEXT

    async def auto_reply_add_text_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        keyword = context.user_data.get("auto_reply_keyword", "")
        reply_text = update.message.text.strip()
        await self.database.add_custom_reply(keyword, reply_text)
        await update.message.reply_text(
            f"✅ تم إضافة الرد التلقائي\n\nالكلمة: {keyword}\nالرد: {reply_text}",
            reply_markup=auto_reply_keyboard(),
        )
        return ConversationHandler.END

    async def auto_reply_delete_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        replies = await self.database.list_custom_replies()
        if not replies:
            await update.callback_query.message.reply_text(
                "لا توجد ردود تلقائية لحذفها",
                reply_markup=auto_reply_keyboard(),
            )
            return ConversationHandler.END

        text = "اختر رقم الرد للحذف:\n\n"
        for reply in replies:
            preview = reply.reply_text[:30] + "..." if len(reply. reply_text) > 30 else reply.reply_text
            text += f"{reply.id}. {reply.keyword} → {preview}\n"
        text += "\nأرسل رقم الرد:"

        await update.callback_query.message.reply_text(text)
        return AUTO_REPLY_DELETE_ID

    async def auto_reply_delete_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            reply_id = int(update.message.text.strip())
            deleted = await self.database.delete_custom_reply(reply_id)
            if deleted:
                await update.message.reply_text("✅ تم حذف الرد التلقائي", reply_markup=auto_reply_keyboard())
            else:
                await update.message.reply_text("❌ الرد غير موجود", reply_markup=auto_reply_keyboard())
        except ValueError:
            await update.message.reply_text("❌ رقم غير صحيح", reply_markup=auto_reply_keyboard())
        return ConversationHandler.END

    # Auto-reply users management handlers
    async def auto_user_add_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل معرف المستخدم (User ID) الذي تريد إضافته للرد التلقائي:\n\n"
            "مثال: 123456789\n\n"
            "يمكنك إيجاد معرف المستخدم بإرسال: @userinfobot"
        )
        return AUTO_USER_ADD_ID

    async def auto_user_add_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            user_id = int(update.message.text.strip())
            # Try to get user info from Telegram
            try:
                client = self.tg_manager.get_active_client()
                user_entity = await client.get_entity(user_id)
                username = getattr(user_entity, "username", None)
                first_name = getattr(user_entity, "first_name", "")
                last_name = getattr(user_entity, "last_name", "")
                full_name = f"{first_name} {last_name}".strip() or None
            except Exception as exc:
                logger.warning(f"Could not fetch user info for {user_id}: {exc}")
                username = None
                full_name = None
            
            await self.database.add_auto_reply_user(user_id, username, full_name)
            await self.auto_reply.reload_users()
            
            user_info = f"معرف: {user_id}"
            if username:
                user_info += f"\nاليوزر: @{username}"
            if full_name:
                user_info += f"\nالاسم: {full_name}"
            
            await update.message.reply_text(
                f"✅ تم إضافة المستخدم للردود التلقائية\n\n{user_info}",
                reply_markup=auto_reply_users_keyboard(),
            )
        except ValueError:
            await update.message.reply_text("❌ معرف غير صحيح", reply_markup=auto_reply_users_keyboard())
        return ConversationHandler.END

    async def auto_user_remove_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        users = await self.database.list_auto_reply_users()
        if not users:
            await update.callback_query.message.reply_text(
                "لا يوجد مستخدمين للحذف",
                reply_markup=auto_reply_users_keyboard(),
            )
            return ConversationHandler.END

        text = "اختر معرف المستخدم للحذف:\n\n"
        for user in users:
            user_info = f"• {user.user_id}"
            if user.username:
                user_info += f" (@{user.username})"
            if user.full_name:
                user_info += f" - {user.full_name}"
            status = "✅" if user.enabled else "❌"
            text += f"{status} {user_info}\n"
        text += "\nأرسل معرف المستخدم:"

        await update.callback_query.message.reply_text(text)
        return AUTO_USER_REMOVE_ID

    async def auto_user_remove_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            user_id = int(update.message.text.strip())
            deleted = await self.database.remove_auto_reply_user(user_id)
            if deleted:
                await self.auto_reply.reload_users()
                await update.message.reply_text("✅ تم حذف المستخدم", reply_markup=auto_reply_users_keyboard())
            else:
                await update.message.reply_text("❌ المستخدم غير موجود", reply_markup=auto_reply_users_keyboard())
        except ValueError:
            await update.message.reply_text("❌ معرف غير صحيح", reply_markup=auto_reply_users_keyboard())
        return ConversationHandler.END

    async def auto_user_toggle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        users = await self.database.list_auto_reply_users()
        if not users:
            await update.callback_query.message.reply_text(
                "لا يوجد مستخدمين للتعديل",
                reply_markup=auto_reply_users_keyboard(),
            )
            return ConversationHandler.END

        text = "اختر معرف المستخدم لتفعيله أو تعطيله:\n\n"
        for user in users:
            user_info = f"• {user.user_id}"
            if user.username:
                user_info += f" (@{user.username})"
            if user.full_name:
                user_info += f" - {user.full_name}"
            status = "✅ مفعّل" if user.enabled else "❌ معطّل"
            text += f"{status} {user_info}\n"
        text += "\nأرسل معرف المستخدم:"

        await update.callback_query.message.reply_text(text)
        return AUTO_USER_TOGGLE_ID

    async def auto_user_toggle_id_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            user_id = int(update.message.text.strip())
            # Get current status
            users = await self.database.list_auto_reply_users()
            user = next((u for u in users if u.user_id == user_id), None)
            if user:
                new_status = not user.enabled
                updated = await self.database.toggle_auto_reply_user(user_id, new_status)
                if updated:
                    await self.auto_reply.reload_users()
                    status_text = "مفعّل" if new_status else "معطّل"
                    await update.message.reply_text(
                        f"✅ تم تحديث حالة المستخدم إلى: {status_text}",
                        reply_markup=auto_reply_users_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ فشل التحديث", reply_markup=auto_reply_users_keyboard())
            else:
                await update.message.reply_text("❌ المستخدم غير موجود", reply_markup=auto_reply_users_keyboard())
        except ValueError:
            await update.message.reply_text("❌ معرف غير صحيح", reply_markup=auto_reply_users_keyboard())
        return ConversationHandler.END

    # Delay configuration conversation handlers
    async def delay_set_min_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل أقل وقت للتأخير بالثواني:\n\n"
            "مثال: 2"
        )
        return DELAY_SET_MIN

    async def delay_set_min_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            min_delay = float(update.message.text.strip())
            await self.database.set_setting("delay_min", str(min_delay))
            await update.message.reply_text(
                f"✅ تم تعيين أقل وقت للتأخير: {min_delay} ثانية",
                reply_markup=delay_keyboard(),
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صحيحة", reply_markup=delay_keyboard())
        return ConversationHandler.END

    async def delay_set_max_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل أعلى وقت للتأخير بالثواني:\n\n"
            "مثال: 5"
        )
        return DELAY_SET_MAX

    async def delay_set_max_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            max_delay = float(update.message.text.strip())
            await self.database.set_setting("delay_max", str(max_delay))
            await update.message.reply_text(
                f"✅ تم تعيين أعلى وقت للتأخير: {max_delay} ثانية",
                reply_markup=delay_keyboard(),
            )
        except ValueError:
            await update.message.reply_text("❌ قيمة غير صحيحة", reply_markup=delay_keyboard())
        return ConversationHandler.END

    # Bulk send conversation handlers
    async def bulk_send_text_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "أرسل نص الرسالة الجماعية:\n\n"
            "سيتم إرسالها لجميع المستخدمين المستخرجين"
        )
        return BULK_TEXT_INPUT

    async def bulk_send_text_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["bulk_message"] = update.message.text
        await update.message.reply_text(
            "أرسل اليوزرات، كل واحد في سطر:\n\n"
            "مثال:\n@user1\n@user2\n@user3\n\n"
            "أو أرسل 'all' لإرسال للجميع"
        )
        return BULK_TARGETS_INPUT

    async def bulk_send_targets_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        message_text = context.user_data.get("bulk_message", "")
        targets_input = update.message.text.strip()

        if targets_input.lower() == "all":
            usernames = await self.database.list_usernames()
            if not usernames:
                await update.message.reply_text(
                    "❌ لا يوجد مستخدمون في قاعدة البيانات.\n"
                    "استخدم أولاً: /extract_group <group_id_or_username>\n"
                    "أو: /extract_private [days]",
                    reply_markup=bulk_keyboard(),
                )
                return ConversationHandler.END
            targets = [f"@{u}" if not u.startswith("@") else u for u in usernames]
        else:
            normalized_input = targets_input.replace("،", ",")
            raw_targets: list[str] = []
            for line in normalized_input.split("\n"):
                for part in line.split(","):
                    candidate = part.strip()
                    if candidate:
                        raw_targets.append(candidate)

            # Accept @username or username and normalize to @username.
            targets = [t if t.startswith("@") else f"@{t}" for t in raw_targets]

        await update.message.reply_text(
            f"جاري الإرسال إلى {len(targets)} مستخدم...\n\n"
            "سيتم إعلامك عند الانتهاء"
        )

        await self.messaging.start()
        result = await self.messaging.send_bulk(
            targets,
            SendPayload(text=message_text),
            mode="username"
        )

        await update.message.reply_text(
            f"✅ انتهى الإرسال الجماعي\n\n"
            f"تم المعالجة: {result['processed']}\n"
            f"نجح: {result['sent']}\n"
            f"فشل: {result['failed']}\n"
            f"متخطى: {result['skipped']}",
            reply_markup=bulk_keyboard(),
        )
        return ConversationHandler.END

    async def conversation_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("تم إلغاء العملية")
        return ConversationHandler.END

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id if query.from_user else None
        if not self._is_fully_authorized(user_id):
            await query.edit_message_text(
                f"Unauthorized. Your Telegram user ID is: {user_id}"
            )
            return

        data = query.data or ""

        if data == "back_dashboard":
            await query.edit_message_text("لوحة التحكم الرئيسية", reply_markup=dashboard_keyboard())
            return

        if data == "menu_welcome":
            await query.edit_message_text("👋 قسم الترحيب", reply_markup=welcome_keyboard())
            return

        if data == "menu_auto_reply":
            await query.edit_message_text("🤖 قسم الردود التلقائية", reply_markup=auto_reply_keyboard())
            return

        if data == "menu_delay":
            await query.edit_message_text("⏱️ إعدادات التأخير", reply_markup=delay_keyboard())
            return

        if data == "menu_rest":
            mode = "مفعّل" if await self._rest_mode() else "متوقف"
            await query.edit_message_text(
                f"🛌 وضع الراحة\n\nالحالة الحالية: {mode}",
                reply_markup=rest_keyboard(),
            )
            return

        if data == "menu_stats":
            await self._show_stats_overview(query)
            return

        if data == "menu_words":
            await self._show_top_words(query)
            return

        if data == "menu_bulk":
            await query.edit_message_text("📢 الإرسال الجماعي", reply_markup=bulk_keyboard())
            return

        if data == "menu_accounts":
            await query.edit_message_text("⚙️ إدارة الحسابات", reply_markup=accounts_keyboard())
            return

        if data == "quick_add_auto_reply":
            await query.edit_message_text(
                "➕ إضافة رد تلقائي\n\nاستخدم الإعداد الحالي من AUTO_REPLY_KEYWORDS في .env.\n"
                "ويمكنك لاحقاً توسعة الحفظ في قاعدة البيانات.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        if data in {
            "welcome_add_message",
            "welcome_delete_message",
            "welcome_change_period",
            "welcome_random_number",
            "welcome_test",
        }:
            # These will be handled by conversation handlers or simple callbacks
            if data == "welcome_change_period":
                await query.edit_message_text(
                    "لتغيير مدة إعادة الترحيب، استخدم:\n"
                    "/set_welcome_period <عدد_الأيام>\n\n"
                    "مثال: /set_welcome_period 7",
                    reply_markup=welcome_keyboard(),
                )
            elif data == "welcome_list_messages":
                messages = await self.database.list_welcome_messages()
                if not messages:
                    text = "لا توجد رسائل ترحيب حالياً"
                else:
                    text = "رسائل الترحيب:\n\n"
                    for msg in messages:
                        status = "✅" if msg.enabled else "❌"
                        preview = msg.content[:40] + "..." if len(msg.content) > 40 else msg.content
                        text += f"{status} {msg.id}. {preview}\n"
                await query.edit_message_text(text, reply_markup=welcome_keyboard())
            elif data == "welcome_test":
                # Send a test welcome message to the admin
                messages = await self.database.list_welcome_messages()
                if messages and messages[0].enabled:
                    await query.message.reply_text(f"رسالة ترحيب تجريبية:\n\n{messages[0].content}")
                else:
                    await query.message.reply_text("لا توجد رسائل ترحيب نشطة")
                await query.edit_message_text("تم إرسال رسالة تجريبية", reply_markup=welcome_keyboard())
            else:
                # welcome_add_message and welcome_delete_message are handled by conversation handlers
                pass
            return

        if data == "welcome_enable":
            await self.database.set_setting("welcome_enabled", "1")
            await query.edit_message_text("تم تشغيل رسائل الترحيب", reply_markup=welcome_keyboard())
            return

        if data == "welcome_disable":
            await self.database.set_setting("welcome_enabled", "0")
            await query.edit_message_text("تم إيقاف رسائل الترحيب", reply_markup=welcome_keyboard())
            return

        if data in {"auto_add", "auto_delete", "auto_edit", "auto_list", "auto_keywords", "auto_random", "auto_image", "auto_video"}:
            if data == "auto_list":
                replies = await self.database.list_custom_replies()
                if not replies:
                    text = "لا توجد ردود تلقائية حالياً"
                else:
                    text = "الردود التلقائية:\n\n"
                    for reply in replies:
                        status = "✅" if reply.enabled else "❌"
                        preview = reply.reply_text[:30] + "..." if len(reply.reply_text) > 30 else reply.reply_text
                        text += f"{status} {reply.id}. {reply.keyword} → {preview}\n"
                await query.edit_message_text(text, reply_markup=auto_reply_keyboard())
            elif data == "auto_keywords":
                await query.edit_message_text(
                    "الكلمات المفتاحية الحالية مضبوطة في .env:\n"
                    f"AUTO_REPLY_KEYWORDS\n\n"
                    "يمكنك إضافة ردود مخصصة من زر 'إضافة رد تلقائي'",
                    reply_markup=auto_reply_keyboard(),
                )
            elif data in {"auto_edit", "auto_random", "auto_image", "auto_video"}:
                await self._show_not_implemented(query, "🤖 قسم الردود التلقائية", auto_reply_keyboard())
            # auto_add and auto_delete handled by conversation handlers
            return

        if data == "auto_enable":
            self.auto_reply.set_enabled(True)
            await self.database.set_setting("auto_reply_enabled", "1")
            await query.edit_message_text("تم تشغيل الردود التلقائية", reply_markup=auto_reply_keyboard())
            return

        if data == "auto_disable":
            self.auto_reply.set_enabled(False)
            await self.database.set_setting("auto_reply_enabled", "0")
            await query.edit_message_text("تم إيقاف الردود التلقائية", reply_markup=auto_reply_keyboard())
            return

        if data == "auto_users_menu":
            await query.edit_message_text("👥 إدارة مستخدمي الردود التلقائية", reply_markup=auto_reply_users_keyboard())
            return

        if data == "auto_user_list":
            users = await self.database.list_auto_reply_users()
            if not users:
                text = "لا يوجد مستخدمين مضافين للردود التلقائية حالياً"
            else:
                text = "👥 المستخدمين المضافين للردود التلقائية:\n\n"
                for user in users:
                    user_info = f"• معرف: {user.user_id}"
                    if user.username:
                        user_info += f"\n  اليوزر: @{user.username}"
                    if user.full_name:
                        user_info += f"\n  الاسم: {user.full_name}"
                    status = "✅ مفعّل" if user.enabled else "❌ معطّل"
                    text += f"{status} {user_info}\n\n"
            await query.edit_message_text(text, reply_markup=auto_reply_users_keyboard())
            return

        if data in {"delay_set_min", "delay_set_max", "delay_disable", "delay_test"}:
            if data == "delay_disable":
                await self.database.set_setting("delay_min", "0")
                await self.database.set_setting("delay_max", "0")
                await query.edit_message_text("تم إلغاء التأخير", reply_markup=delay_keyboard())
            elif data == "delay_test":
                min_delay = float(await self.database.get_setting("delay_min", "1.0"))
                max_delay = float(await self.database.get_setting("delay_max", "3.0"))
                await query.edit_message_text(
                    f"⏱️ إعدادات التأخير الحالية:\n\n"
                    f"أقل وقت: {min_delay} ثانية\n"
                    f"أعلى وقت: {max_delay} ثانية",
                    reply_markup=delay_keyboard(),
                )
            # delay_set_min and delay_set_max handled by conversation handlers
            return

        if data == "rest_enable":
            await self.database.set_setting("rest_mode", "1")
            await query.edit_message_text("تم تشغيل وضع الراحة", reply_markup=rest_keyboard())
            return

        if data == "rest_disable":
            await self.database.set_setting("rest_mode", "0")
            await query.edit_message_text("تم إيقاف وضع الراحة", reply_markup=rest_keyboard())
            return

        if data in {"rest_auto_on", "rest_auto_off"}:
            await self._show_not_implemented(query, "🛌 وضع الراحة", rest_keyboard())
            return

        if data == "stats_received":
            stats = await self.analytics.get_basic_stats()
            await query.edit_message_text(
                f"عدد الرسائل المستلمة: {stats['received_messages']}",
                reply_markup=stats_keyboard(),
            )
            return

        if data == "stats_sent":
            stats = await self.analytics.get_basic_stats()
            await query.edit_message_text(
                f"عدد الردود المرسلة: {stats['sent_messages']}",
                reply_markup=stats_keyboard(),
            )
            return

        if data == "stats_users":
            stats = await self.analytics.get_basic_stats()
            await query.edit_message_text(
                f"عدد المستخدمين: {stats['known_users']}",
                reply_markup=stats_keyboard(),
            )
            return

        if data == "stats_top_users":
            top_users = await self.analytics.top_interacting_users(limit=10)
            text = "\n".join([f"- {user_id}: {count}" for user_id, count in top_users]) or "لا يوجد تفاعل بعد"
            await query.edit_message_text(
                f"أكثر المستخدمين تفاعلاً:\n\n{text}",
                reply_markup=stats_keyboard(),
            )
            return

        if data == "stats_top_words":
            top_words = await self.analytics.top_words(limit=10)
            text = "\n".join([f"- {word}: {count}" for word, count in top_words]) or "لا توجد كلمات حالياً"
            await query.edit_message_text(
                f"أكثر الكلمات استخدام:\n\n{text}",
                reply_markup=stats_keyboard(),
            )
            return

        if data == "stats_reset":
            await self.database.reset_stats()
            await query.edit_message_text("تم تصفير الإحصائيات بنجاح", reply_markup=stats_keyboard())
            return

        if data == "words_show":
            await self._show_top_words(query, title="🔍 عرض أكثر الكلمات")
            return

        if data == "words_reset":
            await self.database.clear_word_corpus()
            await query.edit_message_text("تم تصفير الكلمات بنجاح", reply_markup=words_keyboard())
            return

        if data == "words_export":
            export_path = await self._export_top_words()
            await query.edit_message_text(
                f"تم تصدير الكلمات إلى:\n{export_path}",
                reply_markup=words_keyboard(),
            )
            return

        if data == "send_start":
            await self.messaging.start()
            await query.edit_message_text("تم بدء وضع الإرسال", reply_markup=bulk_keyboard())
            return

        if data == "send_stop":
            await self.messaging.stop()
            await query.edit_message_text("تم إيقاف الإرسال", reply_markup=bulk_keyboard())
            return

        if data in {
            "bulk_send_text",
            "bulk_send_image",
            "bulk_send_video",
            "bulk_send_button",
            "bulk_send_scheduled",
            "bulk_users_only",
            "bulk_group_members",
        }:
            if data == "bulk_users_only":
                usernames = await self.database.list_usernames()
                await query.edit_message_text(
                    f"عدد المستخدمين المستخرجين: {len(usernames)}\n\n"
                    "استخدم 'إرسال رسالة جماعية' للإرسال",
                    reply_markup=bulk_keyboard(),
                )
            elif data == "bulk_group_members":
                await query.edit_message_text(
                    "لاستخراج المستخدمين، استخدم أحد الأوامر:\n"
                    "/extract_group <group_id_or_username>\n"
                    "/extract_private [days]\n\n"
                    "أمثلة:\n"
                    "/extract_group @mygroup\n"
                    "/extract_private 30",
                    reply_markup=bulk_keyboard(),
                )
            elif data in {"bulk_send_image", "bulk_send_video", "bulk_send_button", "bulk_send_scheduled"}:
                await self._show_not_implemented(query, "📢 الإرسال الجماعي", bulk_keyboard())
            # bulk_send_text handled by conversation handler
            return

        if data == "accounts_list":
            sessions = await self.sessions_manager.list_sessions()
            await query.edit_message_text("عرض الحسابات: اختر حساباً", reply_markup=sessions_keyboard(sessions))
            return

        if data == "accounts_switch":
            sessions = await self.sessions_manager.list_sessions()
            await query.edit_message_text("تغيير الحساب النشط: اختر حساباً", reply_markup=sessions_keyboard(sessions))
            return

        if data == "back_accounts":
            await query.edit_message_text("⚙️ إدارة الحسابات", reply_markup=accounts_keyboard())
            return

        if data in {"accounts_delete", "accounts_logout"}:
            if data == "accounts_delete":
                sessions = await self.sessions_manager.list_sessions()
                if len(sessions) <= 1:
                    await query.edit_message_text(
                        "لا يمكن حذف الحساب الوحيد المتبقي",
                        reply_markup=accounts_keyboard(),
                    )
                else:
                    text = "لحذف حساب، استخدم الأمر:\n/delete_account <session_name>\n\nالحسابات المتاحة:\n"
                    for s in sessions:
                        text += f"- {s}\n"
                    await query.edit_message_text(text, reply_markup=accounts_keyboard())
            elif data == "accounts_logout":
                await query.edit_message_text(
                    "لتسجيل خروج حساب، استخدم:\n"
                    "/logout_account <session_name>\n\n"
                    "سيتم حذف ملف الجلسة",
                    reply_markup=accounts_keyboard(),
                )
            return

        if data == "account_add":
            await query.edit_message_text(
                "لإضافة حساب جديد، شغّل هذا الأمر في التيرمنال:\n"
                "python -m app.clients.session_login",
                reply_markup=accounts_keyboard(),
            )
            return

        if data == "users_export":
            export_path = await self._export_usernames()
            await query.edit_message_text(
                f"تم تصدير اليوزرات إلى:\n{export_path}",
                reply_markup=accounts_keyboard(),
            )
            return

        if data.startswith("switch_session:"):
            session_name = data.split(":", 1)[1]
            await self.sessions_manager.set_active_session(session_name)
            await self.tg_manager.start_session(
                session_name,
                self.sessions_manager.session_file(session_name),
            )
            await query.edit_message_text(
                f"تم تغيير الحساب النشط إلى: {session_name}",
                reply_markup=accounts_keyboard(),
            )
            return

    async def _rest_mode(self) -> bool:
        return (await self.database.get_setting("rest_mode", "0")) == "1"

    async def start(self) -> None:
        self.application = Application.builder().token(self.token).build()

        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("auth", self.cmd_auth))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("extract_group", self.cmd_extract_group))
        self.application.add_handler(CommandHandler("extract_private", self.cmd_extract_private))
        self.application.add_handler(CommandHandler("template_save", self.cmd_template_save))
        self.application.add_handler(CommandHandler("template_send", self.cmd_template_send))

        # Conversation handlers for interactive input
        welcome_add_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.welcome_add_start, pattern="^welcome_add_message$")],
            states={
                WELCOME_ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.welcome_add_text_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(welcome_add_conv)

        welcome_delete_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.welcome_delete_start, pattern="^welcome_delete_message$")],
            states={
                WELCOME_DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.welcome_delete_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(welcome_delete_conv)

        auto_reply_add_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.auto_reply_add_start, pattern="^auto_add$")],
            states={
                AUTO_REPLY_ADD_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_reply_add_keyword_received)],
                AUTO_REPLY_ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_reply_add_text_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(auto_reply_add_conv)

        auto_reply_delete_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.auto_reply_delete_start, pattern="^auto_delete$")],
            states={
                AUTO_REPLY_DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_reply_delete_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(auto_reply_delete_conv)

        auto_user_add_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.auto_user_add_start, pattern="^auto_user_add$")],
            states={
                AUTO_USER_ADD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_user_add_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(auto_user_add_conv)

        auto_user_remove_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.auto_user_remove_start, pattern="^auto_user_remove$")],
            states={
                AUTO_USER_REMOVE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_user_remove_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(auto_user_remove_conv)

        auto_user_toggle_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.auto_user_toggle_start, pattern="^auto_user_toggle$")],
            states={
                AUTO_USER_TOGGLE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.auto_user_toggle_id_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(auto_user_toggle_conv)

        delay_min_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.delay_set_min_start, pattern="^delay_set_min$")],
            states={
                DELAY_SET_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.delay_set_min_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(delay_min_conv)

        delay_max_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.delay_set_max_start, pattern="^delay_set_max$")],
            states={
                DELAY_SET_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.delay_set_max_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(delay_max_conv)

        bulk_send_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.bulk_send_text_start, pattern="^bulk_send_text$")],
            states={
                BULK_TEXT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bulk_send_text_received)],
                BULK_TARGETS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.bulk_send_targets_received)],
            },
            fallbacks=[CommandHandler("cancel", self.conversation_cancel)],
        )
        self.application.add_handler(bulk_send_conv)

        # Main callback handler (must be last)
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
