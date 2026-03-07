from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1️⃣ 👋 إدارة رسائل الترحيب", callback_data="menu_welcome"),
                InlineKeyboardButton("2️⃣ 🤖 إدارة الردود التلقائية", callback_data="menu_auto_reply"),
            ],
            [
                InlineKeyboardButton("3️⃣ ⏱️ ضبط وقت التأخير", callback_data="menu_delay"),
                InlineKeyboardButton("4️⃣ 🛌 وضع الراحة", callback_data="menu_rest"),
            ],
            [
                InlineKeyboardButton("5️⃣ 📊 الإحصائيات", callback_data="menu_stats"),
                InlineKeyboardButton("6️⃣ 🔍 أكثر الكلمات", callback_data="menu_words"),
            ],
            [
                InlineKeyboardButton("7️⃣ ➕ إضافة رد تلقائي", callback_data="quick_add_auto_reply"),
                InlineKeyboardButton("8️⃣ 📢 إرسال جماعي", callback_data="menu_bulk"),
            ],
            [
                InlineKeyboardButton("9️⃣ ⚙️ إدارة الحسابات", callback_data="menu_accounts"),
                InlineKeyboardButton("🔟 ➕ إضافة حساب", callback_data="account_add"),
            ],
            [InlineKeyboardButton("📤 تصدير اليوزرات", callback_data="users_export")],
        ]
    )


def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تشغيل الترحيب", callback_data="welcome_enable"),
                InlineKeyboardButton("إيقاف الترحيب", callback_data="welcome_disable"),
            ],
            [
                InlineKeyboardButton("إضافة رسالة ترحيب", callback_data="welcome_add_message"),
                InlineKeyboardButton("حذف رسالة ترحيب", callback_data="welcome_delete_message"),
            ],
            [
                InlineKeyboardButton("عرض رسائل الترحيب", callback_data="welcome_list_messages"),
                InlineKeyboardButton("تغيير مدة إعادة الترحيب", callback_data="welcome_change_period"),
            ],
            [
                InlineKeyboardButton("إرسال ترحيب مع رقم عشوائي", callback_data="welcome_random_number"),
                InlineKeyboardButton("اختبار رسالة الترحيب", callback_data="welcome_test"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def auto_reply_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("إضافة رد تلقائي", callback_data="auto_add"),
                InlineKeyboardButton("حذف رد", callback_data="auto_delete"),
            ],
            [
                InlineKeyboardButton("تعديل رد", callback_data="auto_edit"),
                InlineKeyboardButton("عرض الردود", callback_data="auto_list"),
            ],
            [
                InlineKeyboardButton("تشغيل الردود", callback_data="auto_enable"),
                InlineKeyboardButton("إيقاف الردود", callback_data="auto_disable"),
            ],
            [
                InlineKeyboardButton("رد بالكلمات المفتاحية", callback_data="auto_keywords"),
                InlineKeyboardButton("رد عشوائي من عدة ردود", callback_data="auto_random"),
            ],
            [
                InlineKeyboardButton("رد بالصور", callback_data="auto_image"),
                InlineKeyboardButton("رد بالفيديو", callback_data="auto_video"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def delay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تغيير أقل وقت للرد", callback_data="delay_set_min"),
                InlineKeyboardButton("تغيير أعلى وقت للرد", callback_data="delay_set_max"),
            ],
            [
                InlineKeyboardButton("إلغاء التأخير", callback_data="delay_disable"),
                InlineKeyboardButton("اختبار التأخير", callback_data="delay_test"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def rest_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("تشغيل وضع الراحة", callback_data="rest_enable"),
                InlineKeyboardButton("إيقاف وضع الراحة", callback_data="rest_disable"),
            ],
            [
                InlineKeyboardButton("تحديد وقت تشغيل تلقائي", callback_data="rest_auto_on"),
                InlineKeyboardButton("تحديد وقت إيقاف تلقائي", callback_data="rest_auto_off"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("عدد الرسائل المستلمة", callback_data="stats_received"),
                InlineKeyboardButton("عدد الردود المرسلة", callback_data="stats_sent"),
            ],
            [
                InlineKeyboardButton("عدد المستخدمين", callback_data="stats_users"),
                InlineKeyboardButton("أكثر المستخدمين تفاعلاً", callback_data="stats_top_users"),
            ],
            [
                InlineKeyboardButton("أكثر الكلمات استخدام", callback_data="stats_top_words"),
                InlineKeyboardButton("تصفير الإحصائيات", callback_data="stats_reset"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def words_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("عرض أكثر الكلمات", callback_data="words_show"),
                InlineKeyboardButton("تصفير الكلمات", callback_data="words_reset"),
            ],
            [InlineKeyboardButton("تصدير الكلمات", callback_data="words_export")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def bulk_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("إرسال رسالة جماعية", callback_data="bulk_send_text"),
                InlineKeyboardButton("إرسال صورة جماعية", callback_data="bulk_send_image"),
            ],
            [
                InlineKeyboardButton("إرسال فيديو جماعي", callback_data="bulk_send_video"),
                InlineKeyboardButton("إرسال رسالة مع زر", callback_data="bulk_send_button"),
            ],
            [
                InlineKeyboardButton("إرسال رسالة مجدولة", callback_data="bulk_send_scheduled"),
                InlineKeyboardButton("إرسال إلى المستخدمين فقط", callback_data="bulk_users_only"),
            ],
            [
                InlineKeyboardButton("إرسال إلى أعضاء مجموعة", callback_data="bulk_group_members"),
                InlineKeyboardButton("إيقاف الإرسال", callback_data="send_stop"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def accounts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("عرض الحسابات", callback_data="accounts_list"),
                InlineKeyboardButton("تغيير الحساب النشط", callback_data="accounts_switch"),
            ],
            [
                InlineKeyboardButton("حذف حساب", callback_data="accounts_delete"),
                InlineKeyboardButton("تسجيل خروج حساب", callback_data="accounts_logout"),
            ],
            [
                InlineKeyboardButton("إضافة حساب", callback_data="account_add"),
                InlineKeyboardButton("تصدير اليوزرات", callback_data="users_export"),
            ],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="back_dashboard")],
        ]
    )


def sessions_keyboard(session_names: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(name, callback_data=f"switch_session:{name}")]
        for name in session_names
    ]
    rows.append([InlineKeyboardButton("⬅️ رجوع للحسابات", callback_data="back_accounts")])
    return InlineKeyboardMarkup(rows)
