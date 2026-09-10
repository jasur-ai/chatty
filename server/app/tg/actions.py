"""Chat harakatlari: dialoglar/xabarlar sinxroni, yuborish, o'qilgan qilish."""
import io
import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone
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
            kwargs: dict = {
                "caption": caption or None,
                "reply_to": reply_to_tg_id,
                "force_document": (media_type == "file"),
            }
            if media_type == "voice":
                kwargs["voice_note"] = True
                kwargs.pop("force_document", None)
            elif media_type == "round":
                kwargs["video_note"] = True
                kwargs.pop("force_document", None)
            sent = await client.send_file(entity, tmp.name, **kwargs)
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


async def forward_message(account_id: int, dialog_id: int, msg_tg_id: int, target_dialog_ids: list[int]) -> dict:
    """Xabarni bir nechta chatga forward qiladi."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        src = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        sent = []
        for tid in target_dialog_ids:
            td = (
                await db.execute(select(Dialog).where(Dialog.id == tid, Dialog.account_id == account_id))
            ).scalar_one_or_none()
            if td is None:
                continue
            dst = await client.get_entity(input_peer(td.tg_id, td.peer_type))
            await client.forward_messages(dst, messages=msg_tg_id, from_peer=src)
            sent.append(td.id)
        return {"ok": True, "forwarded_to": sent}


async def search_messages(account_id: int, query: str, limit: int = 30) -> list[dict]:
    """Barcha chatlar bo'yicha qidiruv."""
    client = await _require_client(account_id)
    q = query.strip()
    if not q:
        return []
    async with SessionLocal() as db:
        dialogs = (
            await db.execute(select(Dialog).where(Dialog.account_id == account_id))
        ).scalars().all()
        dm = {d.tg_id: d for d in dialogs}
        results: list[dict] = []
        for d in dialogs:
            entity = await client.get_entity(input_peer(d.tg_id, d.peer_type))
            try:
                async for m in client.iter_messages(entity, search=q, limit=5):
                    if m.action is not None:
                        continue
                    results.append(
                        {
                            "tg_id": m.id,
                            "dialog_id": d.id,
                            "dialog_title": d.title,
                            "text": (m.message or "")[:200],
                            "date": (m.date or datetime.now(timezone.utc)).isoformat(),
                            "out": bool(m.out),
                        }
                    )
            except Exception:
                continue
            if len(results) >= limit:
                break
        results.sort(key=lambda r: r["date"], reverse=True)
        return results[:limit]


async def export_dialog(account_id: int, dialog_id: int, fmt: str = "json") -> dict:
    """Chat tarixini eksport qilish (JSON yoki CSV). R2'ga saqlaydi va key qaytaradi."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        msgs = [m async for m in client.iter_messages(entity, limit=10000)]
        rows = []
        for m in reversed(msgs):
            if m.action is not None:
                continue
            rows.append(
                {
                    "date": (m.date or datetime.now(timezone.utc)).isoformat(),
                    "out": bool(m.out),
                    "text": m.message or "",
                    "media": m.media.__class__.__name__ if m.media else "",
                }
            )

    if fmt == "csv":
        import csv as csv_mod

        buf = io.StringIO()
        w = csv_mod.DictWriter(buf, fieldnames=["date", "out", "text", "media"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
        data = buf.getvalue().encode("utf-8")
        key = storage.put(data, "text/csv", ".csv")
    else:
        data = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        key = storage.put(data, "application/json", ".json")

    return {"key": key, "url": storage.url(key), "format": fmt, "count": len(rows)}


async def analytics(account_id: int) -> dict:
    """Oddiy analitika: xabarlar soni, faol soatlar, kunlik trend."""
    async with SessionLocal() as db:
        msgs = (
            await db.execute(select(Message).where(Message.account_id == account_id))
        ).scalars().all()
        dialogs = (
            await db.execute(select(Dialog).where(Dialog.account_id == account_id))
        ).scalars().all()
    total = len(msgs)
    out_count = sum(1 for m in msgs if m.out)
    by_hour = {}
    by_day = {}
    for m in msgs:
        if m.date:
            by_hour[m.date.hour] = by_hour.get(m.date.hour, 0) + 1
            dk = m.date.strftime("%Y-%m-%d")
            by_day[dk] = by_day.get(dk, 0) + 1
    return {
        "total_messages": total,
        "out_messages": out_count,
        "in_messages": total - out_count,
        "dialogs": len(dialogs),
        "by_hour": by_hour,
        "by_day": dict(sorted(by_day.items())[-30:]),
    }


async def backup_chats(account_id: int) -> dict:
    """Barcha chatlarni JSON ko'rinishida R2'ga zaxiralash."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialogs = (
            await db.execute(select(Dialog).where(Dialog.account_id == account_id))
        ).scalars().all()
        out = []
        for d in dialogs:
            entity = await client.get_entity(input_peer(d.tg_id, d.peer_type))
            msgs = [m async for m in client.iter_messages(entity, limit=1000)]
            out.append(
                {
                    "dialog": d.title,
                    "peer_type": d.peer_type,
                    "messages": [
                        {"date": (m.date or datetime.now(timezone.utc)).isoformat(), "out": bool(m.out), "text": m.message or ""}
                        for m in reversed(msgs)
                        if m.action is None
                    ],
                }
            )
    data = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
    key = storage.put(data, "application/json", ".json")
    return {"key": key, "url": storage.url(key), "dialogs": len(out)}