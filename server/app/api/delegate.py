"""Delegat-bot (vakil) API — begonalar bilan bot orqali suhbat.

Egasi (owner/admin) begona odamlar @chattiey_bot'ga yozgan suhbatlarni shu yerda
ko'radi va javob beradi; javob bot nomidan begonaga yetadi.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select

from ..db import DelegateDialog, DelegateMessage, get_session
from ..notify import notifier, _serialize_delegate_dialog, _serialize_delegate_message
from ..storage import storage
from .deps import require_account, require_admin

router = APIRouter(prefix="/api/delegate", tags=["delegate"])
log = logging.getLogger("chatty.delegate")


class SendIn(BaseModel):
    text: str = ""
    media_type: str = "none"
    file_id: str | None = None


def _msg(m: DelegateMessage) -> dict:
    return _serialize_delegate_message(m)


@router.get("/dialogs")
async def list_dialogs(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    rows = (
        await db.execute(
            select(DelegateDialog)
            .order_by(DelegateDialog.pinned.desc(), DelegateDialog.last_msg_date.desc().nullslast())
        )
    ).scalars().all()
    return {"dialogs": [_serialize_delegate_dialog(d) for d in rows]}


@router.get("/dialogs/{dialog_id}/messages")
async def list_messages(
    dialog_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    q = select(DelegateMessage).where(DelegateMessage.dialog_id == dialog_id)
    if before:
        q = q.where(DelegateMessage.id < before)
    q = q.order_by(DelegateMessage.id.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {"messages": [_msg(m) for m in rows], "has_more": len(rows) >= limit}


@router.post("/dialogs/{dialog_id}/send")
async def send_message(
    dialog_id: int,
    body: SendIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    dlg = (
        await db.execute(select(DelegateDialog).where(DelegateDialog.id == dialog_id))
    ).scalar_one_or_none()
    if dlg is None:
        raise HTTPException(status_code=404, detail="Suhbat topilmadi")

    text = body.text.strip()
    if body.media_type != "none" and body.file_id:
        sent_id = await notifier.send_media(dlg.bot_chat_id, body.file_id, body.media_type, text)
    elif text:
        sent_id = await notifier.send_text(dlg.bot_chat_id, text)
    else:
        raise HTTPException(status_code=400, detail="Bo'sh xabar")

    if sent_id is None:
        raise HTTPException(status_code=502, detail="Xabar yuborilmadi (bot API xatosi)")

    from ..db import utcnow

    out = DelegateMessage(
        dialog_id=dlg.id,
        direction="out",
        text=text,
        media_type=body.media_type,
        file_id=body.file_id,
    )
    db.add(out)
    dlg.last_msg_text = text or (body.media_type if body.media_type != "none" else "")
    dlg.last_msg_date = utcnow()
    dlg.last_out = True
    await db.flush()
    await db.commit()
    await db.refresh(out)
    return {"message": _msg(out), "dialog": _serialize_delegate_dialog(dlg)}


@router.post("/dialogs/{dialog_id}/read")
async def mark_read(
    dialog_id: int,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    dlg = (
        await db.execute(select(DelegateDialog).where(DelegateDialog.id == dialog_id))
    ).scalar_one_or_none()
    if dlg is None:
        raise HTTPException(status_code=404, detail="Suhbat topilmadi")
    dlg.unread_count = 0
    await db.commit()
    return {"ok": True}


@router.get("/media/{message_id}")
async def get_media(
    message_id: int,
    db=Depends(get_session),
):
    """Begona yuborgan media faylni xizmat qiladi (getFile orqali, kesh bilan).

    Auth talab qilinmaydi — <img>/<audio> teglari Authorization sarlavhasini
    yubora olmaydi; media avval keshlanadi va /api/media/{key} orqali ochiq beriladi.
    """
    m = (
        await db.execute(select(DelegateMessage).where(DelegateMessage.id == message_id))
    ).scalar_one_or_none()
    if m is None or not m.file_id:
        raise HTTPException(status_code=404, detail="Media topilmadi")

    # Keshda bo'lsa — darhol beramiz
    if m.media_key and storage.exists(m.media_key):
        try:
            data, ct = storage.get(m.media_key)
            return Response(content=data, media_type=ct)
        except Exception:  # noqa: BLE001
            pass

    data = await notifier.get_file(m.file_id)
    if not data:
        raise HTTPException(status_code=502, detail="Media yuklanmadi")

    ext = _ext_for(m.media_type)
    mime = _mime_for(m.media_type)
    key = storage.put(data, mime, ext)
    m.media_key = key
    await db.commit()
    return Response(content=data, media_type=mime)


def _ext_for(media_type: str) -> str:
    return {
        "photo": ".jpg",
        "voice": ".ogg",
        "audio": ".mp3",
        "video": ".mp4",
        "round": ".mp4",
        "gif": ".mp4",
        "file": ".bin",
        "sticker": ".webp",
    }.get(media_type, ".bin")


def _mime_for(media_type: str) -> str:
    return {
        "photo": "image/jpeg",
        "voice": "audio/ogg",
        "audio": "audio/mpeg",
        "video": "video/mp4",
        "round": "video/mp4",
        "gif": "video/mp4",
        "file": "application/octet-stream",
        "sticker": "image/webp",
    }.get(media_type, "application/octet-stream")
