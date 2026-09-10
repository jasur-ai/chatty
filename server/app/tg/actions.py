"""Chat harakatlari: dialoglar/xabarlar sinxroni, yuborish, o'qilgan qilish."""
import io
import logging
import tempfile
from pathlib import Path

from sqlalchemy import select, update as sa_update
from telethon import functions

from ..db import Dialog, Message, SessionLocal
from ..storage import storage
from ..ws import ws_manager
from .manager import manager
from .sync import (
    input_peer,
    serialize_dialog,
    serialize_message,
    update_dialog_last,
    upsert_dialog,
    upsert_message,
)

log = logging.getLogger("chatty.actions")


async def _require_client(account_id: int):
    client = manager.get(account_id)
    if client is None:
        raise ValueError("Akkaunt ulangan emas")
    return client


async def sync_dialogs(account_id: int, limit: int = 200) -> list[dict]:
    client = await _require_client(account_id)
    async with manager.lock(account_id):
        async with SessionLocal() as db:
            dialogs: list[dict] = []
            async for d in client.iter_dialogs(limit=limit):
                entity = d.entity
                dialog = await upsert_dialog(db, account_id, entity, unread_count=d.unread_count)
                if d.pinned:
                    dialog.pinned = True
                last = d.message
                if last is not None:
                    await update_dialog_last(db, dialog, last, bool(last.out))
                await db.flush()
                dialogs.append(serialize_dialog(dialog))
            await db.commit()
            return dialogs


async def sync_messages(
    account_id: int, dialog_id: int, limit: int = 50, before: int | None = None
) -> tuple[list[dict], bool]:
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))

    msgs = [m async for m in client.iter_messages(entity, limit=limit, offset_id=before or 0)]

    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one()
        rows: list[Message] = []
        for m in msgs:
            if m.action is not None:
                continue
            row = await upsert_message(db, client, account_id, dialog, m)
            rows.append(row)
        await db.commit()
        out = [serialize_message(r) for r in rows]
        return out, len(msgs) >= limit


async def send_text(
    account_id: int, dialog_id: int, text: str, reply_to_tg_id: int | None = None
) -> dict:
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        sent = await client.send_message(entity, text, reply_to=reply_to_tg_id)
        row = await upsert_message(db, client, account_id, dialog, sent)
        await update_dialog_last(db, dialog, sent, True)
        await db.commit()
        payload = {"type": "message", "dialog": serialize_dialog(dialog), "message": serialize_message(row)}
        await ws_manager.broadcast(account_id, payload)
        return serialize_message(row)


async def send_media(
    account_id: int,
    dialog_id: int,
    media_key: str,
    media_type: str,
    caption: str = "",
    reply_to_tg_id: int | None = None,
) -> dict:
    """R2'dagi faylni Telegram'ga media sifatida yuboradi."""
    client = await _require_client(account_id)
    data, content_type = storage.get(media_key)

    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))

        # R2'dan temp faylga chiqarib, Telethon orqali yuboramiz
        ext = Path(media_key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            sent = await client.send_file(
                entity,
                tmp.name,
                caption=caption or None,
                reply_to=reply_to_tg_id,
                force_document=(media_type == "file"),
            )
        finally:
            Path(tmp.name).unlink(missing_ok=True)

        # Xabarni DB'ga yozamiz (media R2'da allaqachon — qayta yuklab olmaymiz)
        row = Message(
            account_id=account_id,
            dialog_id=dialog.id,
            tg_id=sent.id,
            out=True,
            text=caption,
            media_type=media_type,
            media_key=media_key,
            media_size=len(data),
            date=sent.date,
            reply_to=sent.reply_to_msg_id,
            read=False,
        )
        db.add(row)
        await update_dialog_last(db, dialog, sent, True)
        await db.commit()
        await db.refresh(row)
        payload = {"type": "message", "dialog": serialize_dialog(dialog), "message": serialize_message(row)}
        await ws_manager.broadcast(account_id, payload)
        return serialize_message(row)


async def mark_read(account_id: int, dialog_id: int) -> None:
    """Chat ochilganda o'qilgan qilish — faqat shunda! Avtomatik mark_read YO'Q."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            return
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        try:
            await client(functions.messages.MarkDialogAsReadRequest(peer=entity, max_id=0))
        except Exception:
            await client(functions.channels.ReadHistoryRequest(channel=entity, max_id=0))

        await db.execute(
            sa_update(Message)
            .where(Message.dialog_id == dialog.id, Message.out.is_(False), Message.read.is_(False))
            .values(read=True)
        )
        dialog.unread_count = 0
        await db.commit()


async def get_me(account_id: int) -> dict:
    client = await _require_client(account_id)
    me = await client.get_me()
    return {
        "id": me.id,
        "first_name": me.first_name,
        "last_name": me.last_name,
        "username": me.username,
        "phone": me.phone,
    }