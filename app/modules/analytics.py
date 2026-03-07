from __future__ import annotations

import asyncio
import re
from collections import Counter

import pandas as pd
from sqlalchemy import func, select

from app.config import EXPORT_DIR
from app.database import Database, InteractionLog, MessageLog


WORD_RE = re.compile(r"[A-Za-z0-9_\u0600-\u06FF]+")


class AnalyticsService:
    def __init__(self, database: Database) -> None:
        self.database = database
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    async def get_basic_stats(self) -> dict[str, int]:
        return await self.database.dashboard_stats()

    async def top_interacting_users(self, limit: int = 10) -> list[tuple[int, int]]:
        async with self.database.session() as session:
            stmt = (
                select(InteractionLog.user_id, func.count(InteractionLog.id).label("c"))
                .where(InteractionLog.user_id.is_not(None))
                .group_by(InteractionLog.user_id)
                .order_by(func.count(InteractionLog.id).desc())
                .limit(limit)
            )
            rows = await session.execute(stmt)
            return [(int(user_id), int(count)) for user_id, count in rows.all() if user_id is not None]

    async def top_words(self, limit: int = 10) -> list[tuple[str, int]]:
        async with self.database.session() as session:
            stmt = select(InteractionLog.message_text).where(InteractionLog.message_text.is_not(None))
            rows = await session.execute(stmt)
            texts = [row[0] for row in rows.all() if row[0]]

        words: list[str] = []
        for text in texts:
            words.extend([word.lower() for word in WORD_RE.findall(text)])

        return Counter(words).most_common(limit)

    async def export_report(self, filename_stem: str = "report") -> dict[str, str]:
        async with self.database.session() as session:
            sent_rows = await session.execute(select(MessageLog))
            interaction_rows = await session.execute(select(InteractionLog))

        sent_data = [
            {
                "recipient_key": item.recipient_key,
                "status": item.status,
                "message_type": item.message_type,
                "error": item.error,
                "sent_at": item.sent_at,
            }
            for item in sent_rows.scalars()
        ]

        interaction_data = [
            {
                "user_id": item.user_id,
                "direction": item.direction,
                "message_text": item.message_text,
                "created_at": item.created_at,
            }
            for item in interaction_rows.scalars()
        ]

        sent_df = pd.DataFrame(sent_data)
        interactions_df = pd.DataFrame(interaction_data)

        csv_path = EXPORT_DIR / f"{filename_stem}.csv"
        xlsx_path = EXPORT_DIR / f"{filename_stem}.xlsx"

        def _write_reports() -> None:
            sent_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                sent_df.to_excel(writer, index=False, sheet_name="sent")
                interactions_df.to_excel(writer, index=False, sheet_name="interactions")

        await asyncio.to_thread(_write_reports)

        return {"csv": str(csv_path), "xlsx": str(xlsx_path)}
