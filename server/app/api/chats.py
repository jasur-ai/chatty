"""Chatlar, xabarlar va media API."""
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from ..db import AppUser, Dialog, Message, SessionLocal, get_session
from ..storage import storage
from ..tg import actions
from ..tg.sync import media_type_from_content_type
from .deps import require_account, resolve_account_id

router = APIRouter(prefix="/api", tags=["chats"])

MAX_UPLOAD_BYTES = 64 * 1024 * 1024  # 64 MB


class SendIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    text: str = ""
    reply_to: int | None = None
    media_key: str | None = None
    media_type: str | None = None


@router.get("/chats")
async def chats(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        return {"dialogs": await actions.sync_dialogs(acc)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 — xatoni aniq ko'rsatish uchun
        logging.getLogger("chatty").exception("Chatlar yuklashda xato")
        raise HTTPException(status_code=500, detail=f"Chatlarni yuklab bo'lmadi: {e}") from e


@router.get("/chats/{dialog_id}/messages")
async def messages(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        msgs, has_more = await actions.sync_messages(acc, dialog_id, limit=limit, before=before)
        return {"messages": msgs, "has_more": has_more}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/chats/{dialog_id}/read")
async def read(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        await actions.mark_read(acc, dialog_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/messages")
async def send(
    body: SendIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, body.account_id, db)
        if body.media_key:
            return await actions.send_media(
                acc,
                body.dialog_id,
                body.media_key,
                body.media_type or "file",
                caption=body.text,
                reply_to_tg_id=body.reply_to,
            )
        return await actions.send_text(acc, body.dialog_id, body.text, body.reply_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    account_id: int | None = Form(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """App'dan fayl yuklash → R2'ga saqlash. media_key qaytaradi."""
    try:
        acc = await resolve_account_id(token_account, account_id, db)
    except HTTPException:
        raise
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Bo'sh fayl")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Fayl 64 MB dan katta")
    content_type = file.content_type or "application/octet-stream"
    ext = ""
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    key = storage.put(data, content_type, ext)
    media_type = media_type_from_content_type(content_type, file.filename or "")
    return {
        "media_key": key,
        "media_type": media_type,
        "size": len(data),
        "filename": file.filename,
    }


@router.get("/media/fetch/{account_id}/{dialog_id}/{tg_id}")
async def fetch_media(account_id: int, dialog_id: int, tg_id: int):
    """Media'ni talab bo'lganda yuklab beradi (on-demand).

    Xabar yuklanganda media fonda emas, shu endpoint orqali yuklanadi —
    bir xil Telethon client'ni bloklamaydi va rasm/ovoz/video darhol ko'rinadi.
    """
    from ..tg.manager import manager as _mgr
    from ..tg.sync import _process_media, input_peer

    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(Message).where(
                    Message.account_id == account_id,
                    Message.dialog_id == dialog_id,
                    Message.tg_id == tg_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Xabar topilmadi")
        # allaqachon yuklangan bo'lsa — keshdan beramiz
        if row.media_key and storage.exists(row.media_key):
            try:
                data, ct = storage.get(row.media_key)
                return Response(content=data, media_type=ct)
            except Exception:
                pass
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise HTTPException(status_code=404, detail="Dialog topilmadi")
        client = _mgr.get(account_id)
        if client is None:
            raise HTTPException(status_code=503, detail="Akkaunt ulangan emas")
        try:
            entity = await asyncio.wait_for(
                client.get_entity(input_peer(dialog.tg_id, dialog.peer_type)), timeout=15.0
            )
            src = await asyncio.wait_for(client.get_messages(entity, ids=tg_id), timeout=15.0)
            if src is None or not src.media:
                raise HTTPException(status_code=404, detail="Media topilmadi")
            _, new_key = await asyncio.wait_for(_process_media(client, src), timeout=20.0)
            if not new_key:
                raise HTTPException(status_code=502, detail="Media yuklanmadi")
            row.media_key = new_key
            await db.commit()
            data, ct = storage.get(new_key)
            return Response(content=data, media_type=ct)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail="Media yuklanmadi")


@router.get("/media/{key:path}")
async def get_media(key: str):
    """Allaqachon yuklangan media faylni xizmat qilish."""
    try:
        data, content_type = storage.get(key)
        return Response(content=data, media_type=content_type)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="Topilmadi") from e