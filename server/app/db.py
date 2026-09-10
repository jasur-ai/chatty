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
    last_code_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # anti-spam: oxirgi kod so'rovi
    code_attempts: Mapped[int] = mapped_column(Integer, default=0)  # soatdagi urinishlar soni
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
    # Belgilangan odamlarga yuboriladigan alohida avto-javob matni
    auto_reply_selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AutoReplyTarget(Base):
    """Avto-javob faqat shu odamlarga yozadigan "belgilangan" ro'yxat."""

    __tablename__ = "auto_reply_targets"
    __table_args__ = (UniqueConstraint("account_id", "tg_user_id", name="uq_art_account_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WarnState(Base):
    """So'kinish filtri uchun ogohlantirish holati (har bir odam/guruh uchun)."""

    __tablename__ = "warn_states"
    __table_args__ = (UniqueConstraint("account_id", "dialog_id", "user_tg_id", name="uq_warn_account_dialog_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    dialog_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # guruh/chat tg_id; private uchun ham
    user_tg_id: Mapped[int] = mapped_column(BigInteger)
    warns: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MusicPost(Base):
    """Admin joylagan musiqa taklifi — hammaga banner bo'lib chiqadi."""

    __tablename__ = "music_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    performer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2 audio key
    caption: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # admin tg id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MusicReaction(Base):
    """Musiqa taklifiga reaksiya/komment (like/dislike/...)."""

    __tablename__ = "music_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    music_post_id: Mapped[int] = mapped_column(ForeignKey("music_posts.id", ondelete="CASCADE"), index=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger)
    reaction: Mapped[str] = mapped_column(String(16), default="like")  # like|dislike|heart|fire|clap
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Reminder(Base):
    """Lotus AI eslatmalari."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime] = mapped_column(DateTime)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminReport(Base):
    """Admin AI davriy hisobotlari tarixi."""

    __tablename__ = "admin_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    """Global kalit-qiymat sozlamalari."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Admin(Base):
    """Adminlar ro'yxati (owner tomonidan qo'shiladi). tg_user_id bo'yicha."""

    __tablename__ = "admins"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="admin")  # owner|admin
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session