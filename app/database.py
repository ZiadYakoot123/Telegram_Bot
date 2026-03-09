from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import DATA_DIR, settings


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_database_url(raw_url: str) -> str:
    url = raw_url.strip()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite:///") and "aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_interaction: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InteractionLog(Base):
    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(16), index=True)  # sent|received
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MessageLog(Base):
    __tablename__ = "message_logs"
    __table_args__ = (UniqueConstraint("recipient_key", name="uq_message_recipient_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_key: Mapped[str] = mapped_column(String(255), index=True)
    recipient_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)  # sent|failed|skipped
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountSession(Base):
    __tablename__ = "account_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    session_path: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    trigger_type: Mapped[str] = mapped_column(String(16))  # date|interval|cron
    trigger_value: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_type: Mapped[str] = mapped_column(String(32), index=True)  # send|extract|add|error|flood_wait
    status: Mapped[str] = mapped_column(String(32), index=True)  # success|failed|info
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WelcomeMessage(Base):
    __tablename__ = "welcome_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomAutoReply(Base):
    __tablename__ = "custom_auto_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), index=True)
    reply_text: Mapped[str] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # image|video
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutoReplyUser(Base):
    __tablename__ = "auto_reply_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, url: str) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.url = normalize_database_url(url)
        self.engine: AsyncEngine = create_async_engine(self.url, echo=False, future=True)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized at %s", self.url)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def set_setting(self, key: str, value: str) -> None:
        async with self.session() as session:
            existing = await session.get(AppSetting, key)
            if existing is None:
                session.add(AppSetting(key=key, value=value))
            else:
                existing.value = value

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        async with self.session() as session:
            setting = await session.get(AppSetting, key)
            return setting.value if setting else default

    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        phone: str | None,
        last_seen: datetime | None,
        country_code: str | None = None,
    ) -> None:
        async with self.session() as session:
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()
            if profile is None:
                profile = UserProfile(
                    user_id=user_id,
                    username=username,
                    phone=phone,
                    last_seen=last_seen,
                    country_code=country_code,
                )
                session.add(profile)
            else:
                profile.username = username or profile.username
                profile.phone = phone or profile.phone
                profile.last_seen = last_seen or profile.last_seen
                profile.country_code = country_code or profile.country_code

    async def log_interaction(self, user_id: int | None, direction: str, message_text: str | None) -> None:
        async with self.session() as session:
            session.add(InteractionLog(user_id=user_id, direction=direction, message_text=message_text))
            if user_id is not None:
                stmt = select(UserProfile).where(UserProfile.user_id == user_id)
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()
                if profile:
                    profile.last_interaction = utcnow()

    async def log_operation(self, operation_type: str, status: str, details: str | None = None) -> None:
        async with self.session() as session:
            session.add(OperationLog(operation_type=operation_type, status=status, details=details))

    async def has_sent_to_recipient(self, recipient_key: str) -> bool:
        async with self.session() as session:
            stmt = select(MessageLog.id).where(
                MessageLog.recipient_key == recipient_key,
                MessageLog.status == "sent",
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def log_message(
        self,
        recipient_key: str,
        message_type: str,
        status: str,
        recipient_user_id: int | None = None,
        error: str | None = None,
    ) -> None:
        async with self.session() as session:
            session.add(
                MessageLog(
                    recipient_key=recipient_key,
                    recipient_user_id=recipient_user_id,
                    message_type=message_type,
                    status=status,
                    error=error,
                )
            )

    async def save_template(self, name: str, content: str, media_path: str | None = None) -> None:
        async with self.session() as session:
            stmt = select(Template).where(Template.name == name)
            result = await session.execute(stmt)
            template = result.scalar_one_or_none()
            if template is None:
                session.add(Template(name=name, content=content, media_path=media_path))
            else:
                template.content = content
                template.media_path = media_path

    async def get_template(self, name: str) -> Template | None:
        async with self.session() as session:
            result = await session.execute(select(Template).where(Template.name == name))
            return result.scalar_one_or_none()

    async def list_templates(self) -> list[Template]:
        async with self.session() as session:
            result = await session.execute(select(Template).order_by(Template.name.asc()))
            return list(result.scalars())

    async def get_recent_interacted_users(self, days: int) -> list[UserProfile]:
        cutoff = utcnow() - timedelta(days=days)
        async with self.session() as session:
            stmt = (
                select(UserProfile)
                .where(UserProfile.last_interaction.is_not(None), UserProfile.last_interaction >= cutoff)
                .order_by(UserProfile.last_interaction.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars())

    async def dashboard_stats(self) -> dict[str, int]:
        async with self.session() as session:
            sent_count = await session.scalar(select(func.count()).select_from(MessageLog).where(MessageLog.status == "sent"))
            received_count = await session.scalar(
                select(func.count()).select_from(InteractionLog).where(InteractionLog.direction == "received")
            )
            users_count = await session.scalar(select(func.count()).select_from(UserProfile))
        return {
            "sent_messages": int(sent_count or 0),
            "received_messages": int(received_count or 0),
            "known_users": int(users_count or 0),
        }

    async def reset_stats(self) -> None:
        async with self.session() as session:
            await session.execute(delete(MessageLog))
            await session.execute(delete(InteractionLog))
            await session.execute(delete(UserProfile))

    async def clear_word_corpus(self) -> None:
        async with self.session() as session:
            await session.execute(
                update(InteractionLog)
                .where(InteractionLog.message_text.is_not(None))
                .values(message_text=None)
            )

    async def list_usernames(self) -> list[str]:
        async with self.session() as session:
            rows = await session.execute(
                select(UserProfile.username)
                .where(UserProfile.username.is_not(None), UserProfile.username != "")
                .order_by(UserProfile.username.asc())
            )
            usernames = [str(item).strip() for item in rows.scalars() if item and str(item).strip()]

        deduplicated = sorted(set(usernames), key=str.lower)
        return deduplicated

    async def add_welcome_message(self, content: str, media_path: str | None = None) -> None:
        async with self.session() as session:
            session.add(WelcomeMessage(content=content, media_path=media_path))

    async def delete_welcome_message(self, message_id: int) -> bool:
        async with self.session() as session:
            result = await session.execute(select(WelcomeMessage).where(WelcomeMessage.id == message_id))
            msg = result.scalar_one_or_none()
            if msg:
                await session.delete(msg)
                return True
            return False

    async def list_welcome_messages(self) -> list[WelcomeMessage]:
        async with self.session() as session:
            result = await session.execute(select(WelcomeMessage).order_by(WelcomeMessage.created_at.desc()))
            return list(result.scalars())

    async def add_custom_reply(self, keyword: str, reply_text: str, media_path: str | None = None, media_type: str | None = None) -> None:
        async with self.session() as session:
            session.add(CustomAutoReply(keyword=keyword, reply_text=reply_text, media_path=media_path, media_type=media_type))

    async def delete_custom_reply(self, reply_id: int) -> bool:
        async with self.session() as session:
            result = await session.execute(select(CustomAutoReply).where(CustomAutoReply.id == reply_id))
            reply = result.scalar_one_or_none()
            if reply:
                await session.delete(reply)
                return True
            return False

    async def list_custom_replies(self) -> list[CustomAutoReply]:
        async with self.session() as session:
            result = await session.execute(select(CustomAutoReply).order_by(CustomAutoReply.keyword.asc()))
            return list(result.scalars())

    async def get_custom_reply_by_keyword(self, text: str) -> CustomAutoReply | None:
        async with self.session() as session:
            result = await session.execute(
                select(CustomAutoReply)
                .where(CustomAutoReply.enabled.is_(True))
                .order_by(CustomAutoReply.created_at.desc())
            )
            replies = list(result.scalars())
            text_lower = text.lower()
            for reply in replies:
                if reply.keyword.lower() in text_lower:
                    return reply
            return None

    async def add_auto_reply_user(self, user_id: int, username: str | None = None, full_name: str | None = None) -> None:
        async with self.session() as session:
            # Check if user already exists
            result = await session.execute(select(AutoReplyUser).where(AutoReplyUser.user_id == user_id))
            existing = result.scalar_one_or_none()
            if existing:
                # Update existing user
                existing.username = username
                existing.full_name = full_name
                existing.enabled = True
            else:
                # Add new user
                session.add(AutoReplyUser(user_id=user_id, username=username, full_name=full_name))

    async def remove_auto_reply_user(self, user_id: int) -> bool:
        async with self.session() as session:
            result = await session.execute(select(AutoReplyUser).where(AutoReplyUser.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                await session.delete(user)
                return True
            return False

    async def toggle_auto_reply_user(self, user_id: int, enabled: bool) -> bool:
        async with self.session() as session:
            result = await session.execute(select(AutoReplyUser).where(AutoReplyUser.user_id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.enabled = enabled
                return True
            return False

    async def list_auto_reply_users(self) -> list[AutoReplyUser]:
        async with self.session() as session:
            result = await session.execute(select(AutoReplyUser).order_by(AutoReplyUser.created_at.desc()))
            return list(result.scalars())

    async def get_enabled_auto_reply_user_ids(self) -> list[int]:
        async with self.session() as session:
            result = await session.execute(
                select(AutoReplyUser.user_id)
                .where(AutoReplyUser.enabled.is_(True))
            )
            return list(result.scalars())

    async def delete_account_session(self, session_name: str) -> bool:
        async with self.session() as session:
            result = await session.execute(select(AccountSession).where(AccountSession.name == session_name))
            account = result.scalar_one_or_none()
            if account:
                await session.delete(account)
                return True
            return False

    async def close(self) -> None:
        await self.engine.dispose()


db = Database(settings.database_url)
