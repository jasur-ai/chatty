"""Ma'lumotlar bazasi — SQLAlchemy 2.0 async (SQLite dev, Postgres uchun tayyor)."""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings

Path("data").mkdir(exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Account(Base):
    """Ulangan Telegram akkaunt (har biri alohida 'bot-persona')."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    api_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_enc: Mapped[str] = mapped_column(Text, default="")  # Fernet bilan shifrlangan StringSession
    auth_step: Mapped[str] = mapped_column(String(16), default="none")  # none|code_sent|awaiting_2fa|ready
    phone_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Bot-persona sozlamalari (default = akkaunt bilan bir xil, keyin o'zgartiriladi)
    bot_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bot_photo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Dialog(Base):
    """Telegram dialoglarining lokal nusxasi."""

    __tablename__ = "dialogs"
    __table_args__ = (UniqueConstraint("account_id", "tg_id", name="uq_dialog_account_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    peer_type: Mapped[str] = mapped_column(String(12), default="user")  # user|chat|channel
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2 key
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_msg_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_msg_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_out: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    unread_max_id: Mapped[int] = mapped_column(BigInteger, default=0)


class Message(Base):
    """Telegram xabarlarining lokal nusxasi."""

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("account_id", "dialog_id", "tg_id", name="uq_msg_account_dialog_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id", ondelete="CASCADE"), index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    out: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[str] = mapped_column(String(16), default="none")
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2 key
    media_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reply_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)  # outgoing: o'qilganmi; incoming: biz o'qidikmi
    # incoming uchun: filter/hide holati (so'kinish 3+ → yashirin)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class AppUser(Base):
    """Web-app foydalanuvchisi — har bir ulangan akkauntga bog'liq."""

    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), unique=True)
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    theme: Mapped[str] = mapped_column(String(16), default="default")  # default|pink
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    """Global kalit-qiymat sozlamalari."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session