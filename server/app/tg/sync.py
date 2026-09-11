"""Telegram entity'larini lokal DB'ga sinxronlash + serializatsiya."""
import io
import time
from datetime import datetime

from sqlalchemy import select
from telethon.tl.types import (
    Channel,
    Chat,
    Document,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChat,
    PeerChannel,
    PeerUser,
    User,
)

from ..db import Dialog, Message, SessionLocal
from ..storage import storage


# ---------------- media ----------------
def media_type_from_content_type(content_type: str, filename: str = "") -> str:
    """Yuklangan fayl uchun media turi (content-type/extension bo'yicha)."""
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    if ct.startswith("image/"):
        return "photo"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/ogg") or ct.startswith("audio/opus") or name.endswith(".ogg"):
        return "voice"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("text/") or name.endswith((".doc", ".docx", ".pdf", ".txt", ".xls", ".xlsx", ".zip", ".rar")):
        return "file"
    return "file"


def media_type_of(msg) -> str:
    if msg.photo:
        return "photo"
    if msg.video_note:
        return "round"
    if msg.video:
        return "video"
    if msg.voice:
        return "voice"
    if msg.audio:
        return "audio"
    if msg.sticker:
        return "sticker"
    if msg.animation:
        return "gif"
    if msg.document:
        return "file"
    if msg.poll:
        return "poll"
    return "file"


def _mime_ext_of(msg) -> tuple[str, str]:
    media = msg.media
    if isinstance(media, MessageMediaPhoto):
        return "image/jpeg", ".jpg"
    if isinstance(media, MessageMediaDocument):
        doc: Document = media.document
        mime = doc.mime_type or "application/octet-stream"
        ext = ""
        if doc.attributes:
            for attr in doc.attributes:
                if hasattr(attr, "file_name") and attr.file_name:
                    ext = "." + attr.file_name.rsplit(".", 1)[-1]
        if not ext:
            ext = {  # noqa: SIM116 — ketma-ket tekshirish o'qishga oson
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
            }.get(mime, ".bin")
        return mime, ext
    return "application/octet-stream", ".bin"


async def _process_media(client, msg, deadline: float | None = None) -> tuple[str, str | None]:
    """Media'ni yuklab olib saqlaydi. (media_type, key) qaytaradi.

    deadline berilsa va o'tib ketgan bo'lsa — yuklashni o'tkazib yuboramiz
    (xabar tez qaytishi uchun; media keyin fonda yuklanadi).
    download_media ni wait_for bilan cheklaymiz — katta fayl abadiy bloklamasin.
    """
    import asyncio as _asyncio

    if not msg.media:
        return "none", None
    if deadline is not None and time.monotonic() > deadline:
        return media_type_of(msg), None
    try:
        data = await _asyncio.wait_for(
            client.download_media(msg, file=io.BytesIO()), timeout=6.0
        )
        if data is None:
            return media_type_of(msg), None
        content = data.getvalue() if isinstance(data, io.BytesIO) else bytes(data)
        if not content:
            return media_type_of(msg), None
        mime, ext = _mime_ext_of(msg)
        key = storage.put(content, mime, ext)
        return media_type_of(msg), key
    except Exception:
        return media_type_of(msg), None


# ---------------- peers ----------------
def peer_type_of(entity) -> str:
    if isinstance(entity, User):
        return "user"
    if isinstance(entity, Channel):
        return "channel"
    if isinstance(entity, Chat):
        return "chat"
    return "user"


def input_peer(tg_id: int, peer_type: str):
    if peer_type == "user":
        return PeerUser(tg_id)
    if peer_type == "chat":
        return PeerChat(tg_id)
    return PeerChannel(tg_id)


# ---------------- DB upserts ----------------
async def upsert_dialog(db, account_id: int, entity, *, unread_count: int = 0) -> Dialog:
    tg_id = entity.id
    peer_type = peer_type_of(entity)
    row = (
        await db.execute(
            select(Dialog).where(Dialog.account_id == account_id, Dialog.tg_id == tg_id)
        )
    ).scalar_one_or_none()
    title = getattr(entity, "title", None) or getattr(entity, "first_name", "") or ""
    username = getattr(entity, "username", None)
    if row is None:
        row = Dialog(
            account_id=account_id,
            tg_id=tg_id,
            peer_type=peer_type,
            title=title,
            username=username,
            unread_count=unread_count,
        )
        db.add(row)
    else:
        row.title = title
        row.username = username
        row.peer_type = peer_type
        row.unread_count = unread_count
    await db.flush()
    return row


async def download_dialog_photo(client, entity, db, dialog: Dialog) -> None:
    """Dialog avatar rasmini yuklab olib saqlaydi (kichik rasm — tez)."""
    try:
        photo = getattr(entity, "photo", None)
        if photo is None:
            return
        # download_big=False — kichik (thumbnail) versiya, chatlar ro'yxati uchun yetarli va tez
        data = await client.download_profile_photo(entity, file=io.BytesIO(), download_big=False)
        if data is None:
            return
        content = data.getvalue() if isinstance(data, io.BytesIO) else bytes(data)
        if not content:
            return
        key = storage.put(content, "image/jpeg", ".jpg")
        dialog.photo_key = key
    except Exception:
        # avatar yuklab bo'lmasa o'tkazib yuboramiz (xato emas)
        return


async def upsert_message(
    db, client, account_id: int, dialog: Dialog, msg, *, hidden: bool = False, media_deadline: float | None = None
) -> Message:
    tg_id = msg.id
    row = (
        await db.execute(
            select(Message).where(
                Message.account_id == account_id,
                Message.dialog_id == dialog.id,
                Message.tg_id == tg_id,
            )
        )
    ).scalar_one_or_none()

    text = msg.message or ""
    media_type, media_key = ("none", None)
    need_download = (
        msg.media
        and media_deadline != 0
        and (not row or (row and (row.media_type == "none" or row.media_key is None)))
    )
    if msg.media:
        media_type = media_type_of(msg)
    if need_download:
        media_type, media_key = await _process_media(client, msg, deadline=media_deadline)

    if row is None:
        row = Message(
            account_id=account_id,
            dialog_id=dialog.id,
            tg_id=tg_id,
            out=bool(msg.out),
            text=text,
            media_type=media_type or "none",
            media_key=media_key,
            media_size=getattr(msg.media, "size", None) if msg.media else None,
            date=msg.date or datetime.now(),
            reply_to=msg.reply_to_msg_id,
            read=False,
            hidden=hidden,
        )
        db.add(row)
    else:
        row.text = text
        row.out = bool(msg.out)
        row.reply_to = msg.reply_to_msg_id
        if media_type != "none":
            row.media_type = media_type
        # media_key faqat yangi yuklangan bo'lsa yangilanadi (eski qiymatni yo'qotmaymiz)
        if media_key is not None:
            row.media_key = media_key
    await db.flush()
    return row


async def update_dialog_last(db, dialog: Dialog, msg, out: bool) -> None:
    dialog.last_msg_id = msg.id
    dialog.last_msg_text = (msg.message or "")[:300]
    dialog.last_msg_date = msg.date
    dialog.last_out = out


# ---------------- serialization ----------------
def serialize_dialog(d: Dialog) -> dict:
    photo = None
    if d.photo_key and storage.exists(d.photo_key):
        photo = storage.url(d.photo_key)
    return {
        "id": d.id,
        "tg_id": d.tg_id,
        "type": d.peer_type,
        "title": d.title,
        "username": d.username,
        "unread_count": d.unread_count,
        "last_msg_id": d.last_msg_id,
        "last_msg_text": d.last_msg_text,
        "last_msg_date": d.last_msg_date.isoformat() if d.last_msg_date else None,
        "last_out": d.last_out,
        "pinned": d.pinned,
        "muted": d.muted,
        "photo": photo,
    }


_FETCHABLE_MEDIA = {"photo", "video", "round", "voice", "audio", "gif", "sticker"}


def serialize_message(m: Message) -> dict:
    media_url = None
    if m.media_key and storage.exists(m.media_key):
        # fayl mavjud — to'g'ridan-to'g'ri xizmat qilamiz
        media_url = storage.url(m.media_key)
    elif m.media_type in _FETCHABLE_MEDIA:
        # fayl hali yuklanmagan yoki o'chib ketgan — browser so'raganda yuklanadi (on-demand)
        media_url = f"/api/media/fetch/{m.account_id}/{m.dialog_id}/{m.tg_id}"
    return {
        "id": m.id,
        "tg_id": m.tg_id,
        "dialog_id": m.dialog_id,
        "out": m.out,
        "text": m.text,
        "media_type": m.media_type,
        "media_url": media_url,
        "media_size": m.media_size,
        "date": m.date.isoformat() if m.date else None,
        "reply_to": m.reply_to,
        "read": m.read,
        "hidden": m.hidden,
    }


def serialize_account(a) -> dict:
    return {
        "id": a.id,
        "phone": a.phone,
        "first_name": a.first_name,
        "username": a.username,
        "bot_name": a.bot_name or a.first_name,
        "bot_photo": a.bot_photo,
        "auth_step": a.auth_step,
        "is_active": a.is_active,
    }