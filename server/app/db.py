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
    last_code_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # anti-spam: oxirgi kod so'rovi
    code_attempts: Mapped[int] = mapped_column(Integer, default=0)  # soatdagi urinishlar soni
    # Login davomida ishlatilayotgan StringSession (shifrlangan). Server qayta
    # ishga tushsa ham kodni tekshirish ishlashi uchun bazada saqlanadi —
    # aks holda kod kelguncha process restart bo'lsa, kod hech qachon
    # tasdiqlanmasdi ("Avval kod yuborilishi kerak").
    pending_session: Mapped[str] = mapped_column(Text, default="")
    code_sent_via: Mapped[str | None] = mapped_column(String(16), nullable=True)  # app|sms|call|flash
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Bot-persona sozlamalari (default = akkaunt bilan bir xil, keyin o'zgartiriladi)
    bot_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bot_photo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Dialog(Base):
    """Telegram dialoglarining lokal nusxasi."""

    __tablename__ = "dialogs"
    __table_args__ = (UniqueConstraint("account_id", "tg_id", name="uq_dialog_account_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    peer_type: Mapped[str] = mapped_column(String(12), default="user")  # user|chat|channel
    # Bo'lim: bot|user|group|channel (ChatList'dagi "Botlar/Chatlar/Guruhlar/Kanallar")
    kind: Mapped[str | None] = mapped_column(String(12), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2 key
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_msg_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_msg_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_out: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
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
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reply_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)  # outgoing: o'qilganmi; incoming: biz o'qidikmi
    # incoming uchun: yashirinlik belgisi (hozir doim False; filtrlar olib tashlangan)
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
    # Avto-javob jadvali (masalan "09:00-18:00"); bo'sh = doim
    auto_reply_from: Mapped[str | None] = mapped_column(String(5), nullable=True)
    auto_reply_to: Mapped[str | None] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScheduledMessage(Base):
    """Rejalashtirilgan xabar — ma'lum vaqtda avtomatik yuboriladi."""

    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutoDeleteRule(Base):
    """Avto-o'chirish: yuborilgan xabarlar N soniyadan keyin o'chiriladi."""

    __tablename__ = "auto_delete_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), unique=True)
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=0)  # 0 = o'chirilgan
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StarredMessage(Base):
    """Yulduzchalangan (xatcho'p) xabarlar — VIP."""

    __tablename__ = "starred_messages"
    __table_args__ = (UniqueConstraint("account_id", "dialog_id", "tg_id", name="uq_star_acc_dialog_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    dialog_id: Mapped[int] = mapped_column(BigInteger)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text, default="")
    dialog_title: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QuickReply(Base):
    """Tezkor javoblar (shablon) — VIP."""

    __tablename__ = "quick_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutoForwardRule(Base):
    """Avto-forward qoidasi: kalit so'z bo'lsa xabarni boshqa chatga yo'naltirish — VIP."""

    __tablename__ = "auto_forward_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    keyword: Mapped[str] = mapped_column(String(128), default="")
    source_dialog_id: Mapped[int] = mapped_column(BigInteger, default=0)  # 0 = barcha chatlar
    target_dialog_id: Mapped[int] = mapped_column(BigInteger)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VipTheme(Base):
    """VIP shaxsiy mavzu (rang sozlamalari)."""

    __tablename__ = "vip_themes"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    accent: Mapped[str] = mapped_column(String(16), default="#3390ec")
    name: Mapped[str] = mapped_column(String(32), default="custom")


class AutoReplyTarget(Base):
    """Avto-javob faqat shu odamlarga yozadigan "belgilangan" ro'yxat."""

    __tablename__ = "auto_reply_targets"
    __table_args__ = (UniqueConstraint("account_id", "tg_user_id", name="uq_art_account_tg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MusicReaction(Base):
    """Musiqa taklifiga reaksiya/komment (like/dislike/...)."""

    __tablename__ = "music_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    music_post_id: Mapped[int] = mapped_column(ForeignKey("music_posts.id", ondelete="CASCADE"), index=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger)
    reaction: Mapped[str] = mapped_column(String(16), default="like")  # like|dislike|heart|fire|clap
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reminder(Base):
    """Lotus AI eslatmalari."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventFolderConfig(Base):
    """Tadbir/event skaneri uchun tanlangan Telegram papka sozlamasi.

    Har bir akkaunt bitta papkaga ega (kanallar/guruhlar to'plami). Shu papkadagi
    barcha kanal/guruhlar so'nggi `days` kunlik xabarlari kalit so'zlar bo'yicha
    tekshiriladi.
    """

    __tablename__ = "event_folder_configs"
    __table_args__ = (UniqueConstraint("account_id", name="uq_efc_account"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[int] = mapped_column(Integer, default=0)  # Telegram dialog filtri id'si
    folder_title: Mapped[str] = mapped_column(String(128), default="")
    days: Mapped[int] = mapped_column(Integer, default=7)
    # Qo'shimcha kalit so'zlar (vergul bilan) — standart lug'atga qo'shiladi
    extra_keywords: Mapped[str] = mapped_column(Text, default="")
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventItem(Base):
    """Skaner topgan bitta tadbir/event (jadvaldagi bir qator)."""

    __tablename__ = "event_items"
    __table_args__ = (
        UniqueConstraint("account_id", "dialog_tg_id", "msg_tg_id", name="uq_event_acc_dialog_msg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    dialog_tg_id: Mapped[int] = mapped_column(BigInteger)
    source_title: Mapped[str] = mapped_column(String(255), default="")
    source_kind: Mapped[str] = mapped_column(String(12), default="channel")  # channel|group
    msg_tg_id: Mapped[int] = mapped_column(BigInteger)
    msg_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="")  # tadbir nomi
    purpose: Mapped[str] = mapped_column(Text, default="")  # maqsadi/tavsifi
    when_: Mapped[str] = mapped_column("when_", String(255), default="")  # vaqti
    place: Mapped[str] = mapped_column(String(255), default="")  # o'tkaziladigan joyi
    text: Mapped[str] = mapped_column(Text, default="")  # asl xabar matni
    by_ai: Mapped[bool] = mapped_column(Boolean, default=False)  # AI tomonidan aniqlashtirilganmi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminReport(Base):
    """Admin AI davriy hisobotlari tarixi."""

    __tablename__ = "admin_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    """Global kalit-qiymat sozlamalari."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class DelegateDialog(Base):
    """Delegat-bot suhbati: begona odam @chattiey_bot'ga yozgan shaxsiy chat.

    Bot egasi (owner) bu suhbatlarni mini app'da ko'radi va javob beradi —
    javob bot nomidan begonaga yetib boradi (vakil/delegate).
    """

    __tablename__ = "delegate_dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # begonaning Telegram chat_id
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_msg_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_msg_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_out: Mapped[bool] = mapped_column(Boolean, default=False)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DelegateMessage(Base):
    """Delegat-bot suhbatidagi bitta xabar (begona ↔ bot egasi)."""

    __tablename__ = "delegate_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("delegate_dialogs.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(4), default="in")  # in = begonadan, out = egadan
    text: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[str] = mapped_column(String(16), default="none")  # none|photo|voice|video|file|...
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)  # Telegram bot API file_id
    # Bot egasiga forward qilingan xabarning message_id (Telegram'da reply orqali javob uchun)
    owner_notify_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BotReplyCtx(Base):
    """Bot ichida javob berish uchun kontekst.

    Push-xabarnoma (yoki begona xabari) bot chatida yuborilganda uning
    message_id'si shu yerda saqlanadi. Egasi shu xabarga reply yozsa,
    javob aynan shu dialogga (MTProto orqali) yetkaziladi — saytga
    yo'naltirmasdan, to'g'ridan-to'g'ri Telegram ichida.
    """

    __tablename__ = "bot_reply_ctx"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_message_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(12), default="chat")  # chat|delegate
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # chat uchun
    dialog_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # chat uchun
    msg_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # reply_to uchun
    delegate_dialog_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # delegate uchun
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Admin(Base):
    """Adminlar ro'yxati (owner tomonidan qo'shiladi). tg_user_id bo'yicha."""

    __tablename__ = "admins"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="admin")  # owner|admin
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _migrate(conn) -> None:
    """Yengil migratsiya: mavjud jadvalga yangi ustunlarni qo'shish.

    SQLite (dev) va Postgres (Neon) ikkalasida ham ishlaydi —
    SQLAlchemy inspector orqali ustunlar tekshiriladi.
    """
    import sqlalchemy as sa  # noqa: PLC0415

    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    def _cols(table: str) -> set[str]:
        return {c["name"] for c in insp.get_columns(table)}

    if "app_users" in tables:
        cols = _cols("app_users")
        if "auto_reply_from" not in cols:
            conn.execute(sa.text("ALTER TABLE app_users ADD COLUMN auto_reply_from VARCHAR(5)"))
        if "auto_reply_to" not in cols:
            conn.execute(sa.text("ALTER TABLE app_users ADD COLUMN auto_reply_to VARCHAR(5)"))
    if "dialogs" in tables:
        cols = _cols("dialogs")
        if "archived" not in cols:
            conn.execute(sa.text("ALTER TABLE dialogs ADD COLUMN archived BOOLEAN DEFAULT 0"))
        if "kind" not in cols:
            conn.execute(sa.text("ALTER TABLE dialogs ADD COLUMN kind VARCHAR(12)"))


async def init_db() -> None:
    async with engine.begin() as conn:
        # Yangi ustunlar (mavjud DB'da create_all ularni qo'shmaydi)
        try:
            await conn.run_sync(_migrate)
        except Exception:
            pass  # yangi DB bo'lsa jadval hali yo'q — create_all yaratadi
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session