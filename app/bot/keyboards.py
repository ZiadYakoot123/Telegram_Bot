from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def dashboard_keyboard(rest_mode: bool) -> InlineKeyboardMarkup:
    rest_label = "Rest Mode: ON" if rest_mode else "Rest Mode: OFF"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Start Sending", callback_data="send_start"),
                InlineKeyboardButton("Stop Sending", callback_data="send_stop"),
            ],
            [InlineKeyboardButton(rest_label, callback_data="rest_toggle")],
            [
                InlineKeyboardButton("Stats", callback_data="stats"),
                InlineKeyboardButton("Templates", callback_data="templates"),
            ],
            [InlineKeyboardButton("Accounts / Sessions", callback_data="accounts")],
        ]
    )


def sessions_keyboard(session_names: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(name, callback_data=f"switch_session:{name}")]
        for name in session_names
    ]
    rows.append([InlineKeyboardButton("Back", callback_data="back_dashboard")])
    return InlineKeyboardMarkup(rows)
