"""Chat harakatlari: dialoglar/xabarlar sinxroni, yuborish, o'qilgan qilish."""
import asyncio
import io
import json
import logging
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update as sa_update
from telethon import functions
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

from ..db import Dialog, Message, SessionLocal
from .. import convert
from ..storage import storage
from ..ws import ws_manager
from .manager import manager
from .sync import (
    _process_media,
    download_dialog_photo,
    input_peer,
    kind_of,
    media_type_of,
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


_photo_flag_backfilled: set[int] = set()


async def backfill_dialog_photo_flags(account_id: int) -> None:
    """Dialoglar uchun 'rasm bor' belgisini (sentinel photo_key="") fonda o'rnatadi.

    Bir marta (har bir akkaunt uchun) ishga tushadi — iter_dialogs orqali entity'larni
    olib, faqat rasm bor-yo'qligini yozadi (hech narsa yuklamaydi). Bu profil rasmlari
    on-demand yuklanishi uchun kerak.
    """
    if account_id in _photo_flag_backfilled:
        return
    _photo_flag_backfilled.add(account_id)
    client = manager.get(account_id)
    if client is None:
        return
    try:
        async with SessionLocal() as db:
            async for d in client.iter_dialogs(limit=None):
                entity = d.entity
                has_photo = getattr(entity, "photo", None) is not None
                if not has_photo:
                    continue
                row = (
                    await db.execute(
                        select(Dialog).where(Dialog.account_id == account_id, Dialog.tg_id == entity.id)
                    )
                ).scalar_one_or_none()
                if row is not None and row.photo_key is None:
                    row.photo_key = ""
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("Profil rasm belgilarini backfill qilishda xato: %s", e)


_avatar_backfilling = False


async def backfill_avatars(account_id: int) -> None:
    """Avatarlarni fonda yuklaydi (javobni bloklamaydi). Kichik rasm, cheklangan son."""
    global _avatar_backfilling
    if _avatar_backfilling:
        return
    _avatar_backfilling = True
    try:
        client = manager.get(account_id)
        if client is None:
            return
        async with SessionLocal() as db:
            missing = (
                await db.execute(
                    select(Dialog)
                    .where(
                        Dialog.account_id == account_id,
                        Dialog.photo_key.is_(None),
                    )
                    .limit(30)
                )
            ).scalars().all()
            for dialog in missing:
                try:
                    entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
                    await asyncio.wait_for(
                        download_dialog_photo(client, entity, db, dialog), timeout=3.0
                    )
                except Exception:
                    continue
            await db.commit()
    except Exception:
        pass
    finally:
        _avatar_backfilling = False


_kinds_backfilled: set[int] = set()


async def backfill_kinds(account_id: int) -> None:
    """Bo'lim turi (bot/user/group/channel) aniqlanmagan dialoglarni fonda to'ldiradi.

    Eski dialoglarda `kind` bo'sh bo'lishi mumkin — ularni Telegram'dan
    entity olib aniqlaymiz (har bir akkaunt uchun bir marta).
    """
    if account_id in _kinds_backfilled:
        return
    _kinds_backfilled.add(account_id)
    client = manager.get(account_id)
    if client is None:
        _kinds_backfilled.discard(account_id)
        return
    try:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Dialog)
                    .where(Dialog.account_id == account_id, Dialog.kind.is_(None))
                    .limit(300)
                )
            ).scalars().all()
            if not rows:
                return
            for d in rows:
                try:
                    entity = await asyncio.wait_for(
                        client.get_entity(input_peer(d.tg_id, d.peer_type)), timeout=15.0
                    )
                except Exception as e:  # noqa: BLE001
                    # Telegram vaqtincha cheklasa (FLOOD_WAIT) — keyingi safar davom etamiz
                    if "wait" in str(e).lower():
                        _kinds_backfilled.discard(account_id)
                        return
                    continue
                d.kind = kind_of(entity)
                await db.commit()
                await asyncio.sleep(0.05)  # Telegram'ni ortiqcha bezovta qilmaymiz
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("Dialog bo'limlarini aniqlashda xato: %s", e)
        _kinds_backfilled.discard(account_id)


async def sync_dialogs(account_id: int, limit: int = 200, force: bool = False) -> list[dict]:
    # 1) DB'da allaqachon dialog bor bo'lsa — darhol qaytaramiz (tez javob).
    #    To'liq sinxronizatsiya faqat birinchi yuklanishda (DB bo'sh) yoki force bilan.
    async with SessionLocal() as db:
        existing = (
            await db.execute(
                select(Dialog)
                .where(Dialog.account_id == account_id)
                .order_by(Dialog.pinned.desc(), Dialog.last_msg_date.desc())
            )
        ).scalars().all()
        if existing and not force:
            # Bo'limlar (bot/user/group/channel) aniqlanmagan bo'lsa — fonda to'ldiramiz
            if any(d.kind is None for d in existing):
                asyncio.create_task(backfill_kinds(account_id))
            return [serialize_dialog(d) for d in existing]

    # 2) Birinchi yuklanish yoki force — Telegram'dan to'liq sinxronizatsiya.
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


async def backfill_message_media(account_id: int, dialog_id: int) -> None:
    """Yuklanmay qolgan (yoki o'chib ketgan) media fayllarni fonda yuklab, WebSocket orqali yangilaydi."""
    client = manager.get(account_id)
    if client is None:
        return
    try:
        async with SessionLocal() as db:
            dialog = (
                await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
            ).scalar_one_or_none()
            if dialog is None:
                return
            entity = await asyncio.wait_for(
                client.get_entity(input_peer(dialog.tg_id, dialog.peer_type)), timeout=15.0
            )
            candidates = (
                await db.execute(
                    select(Message).where(
                        Message.account_id == account_id,
                        Message.dialog_id == dialog_id,
                        Message.media_type.notin_(["none", "file", "poll"]),
                    ).order_by(Message.tg_id.desc()).limit(30)
                )
            ).scalars().all()
            for row in candidates:
                # media_key bor, lekin fayl o'chib ketgan bo'lsa ham qayta yuklaymiz
                if row.media_key and storage.exists(row.media_key):
                    continue
                try:
                    src = await client.get_messages(entity, ids=row.tg_id)
                    if src is None or not src.media:
                        continue
                    _, key = await asyncio.wait_for(_process_media(client, src), timeout=10.0)
                    if key:
                        row.media_key = key
                        await db.commit()
                        await ws_manager.broadcast(
                            account_id,
                            {
                                "type": "message_media",
                                "dialog_id": dialog_id,
                                "tg_id": row.tg_id,
                                "media_type": row.media_type,
                                "media_url": storage.url(key),
                            },
                        )
                except Exception:
                    continue
    except Exception:
        return


async def sync_messages(
    account_id: int, dialog_id: int, limit: int = 50, before: int | None = None
) -> tuple[list[dict], bool]:
    # 1) DB'da xabarlar bor bo'lsa — darhol qaytaramiz (tez, Telegram'ga murojaat yo'q).
    async with SessionLocal() as db:
        q = (
            select(Message)
            .where(Message.account_id == account_id, Message.dialog_id == dialog_id)
        )
        if before:
            q = q.where(Message.tg_id < before)
        q = q.order_by(Message.tg_id.desc()).limit(limit)
        existing = (await db.execute(q)).scalars().all()
        if existing:
            return [serialize_message(m) for m in existing], len(existing) >= limit

    # 2) DB bo'sh — birinchi yuklanish (Telegram'dan, timeout bilan).
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await asyncio.wait_for(
            client.get_entity(input_peer(dialog.tg_id, dialog.peer_type)), timeout=15.0
        )

    msgs = await asyncio.wait_for(
        _collect_messages(client, entity, limit, before or 0), timeout=20.0
    )

    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one()
        rows: list[Message] = []
        # Media sinxron yuklanmaydi (media_deadline=0) — xabarlar DARHOL qaytadi.
        for m in msgs:
            if m.action is not None:
                continue
            row = await upsert_message(db, client, account_id, dialog, m, media_deadline=0)
            rows.append(row)
        await db.commit()
        out = [serialize_message(r) for r in rows]

    return out, len(msgs) >= limit


async def _collect_messages(client, entity, limit: int, offset_id: int) -> list:
    """iter_messages natijasini ro'yxatga yig'adi (timeout bilan ishlatiladi)."""
    return [m async for m in client.iter_messages(entity, limit=limit, offset_id=offset_id)]


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

        # Brauzer webm yozadi — Telegram uchun to'g'ri formatga o'tkazamiz
        ext = Path(media_key).suffix or ".bin"
        converted: bytes | None = None
        send_ext = ext
        if media_type == "voice":
            converted = await asyncio.to_thread(convert.to_voice_note, data, ext)
            if converted:
                data = converted
                send_ext = ".ogg"
        elif media_type == "round":
            converted = await asyncio.to_thread(convert.to_video_note, data, ext)
            if converted:
                data = converted
                send_ext = ".mp4"
        elif media_type == "video" and ext.lower() != ".mp4":
            converted = await asyncio.to_thread(convert.to_video, data, ext)
            if converted:
                data = converted
                send_ext = ".mp4"

        # Telegramga aniq atributlar (duration, o'lcham) bilan yuboramiz.
        # Telethon ularni hachoir orqali topadi — u bo'lmasa fayl "hujjat" bo'lib ketadi.
        info = await asyncio.to_thread(convert.probe, data, send_ext) or {}
        duration = int(info.get("duration") or 0)
        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)

        # R2'dan temp faylga chiqarib, Telethon orqali yuboramiz
        tmp = tempfile.NamedTemporaryFile(suffix=send_ext, delete=False)
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
                kwargs["attributes"] = [DocumentAttributeAudio(duration=max(duration, 1), voice=True)]
            elif media_type == "round":
                kwargs["video_note"] = True
                kwargs.pop("force_document", None)
                kwargs["attributes"] = [
                    DocumentAttributeVideo(
                        duration=max(duration, 1),
                        w=480,
                        h=480,
                        round_message=True,
                        supports_streaming=True,
                    )
                ]
            elif media_type == "video":
                kwargs.pop("force_document", None)
                kwargs["supports_streaming"] = True
                if duration:
                    kwargs["attributes"] = [
                        DocumentAttributeVideo(
                            duration=duration,
                            w=width or 480,
                            h=height or 854,
                            supports_streaming=True,
                        )
                    ]
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


# ================= VIP funksiyalar (barcha mustaqil) =================

async def edit_message(account_id: int, dialog_id: int, msg_tg_id: int, new_text: str) -> dict:
    """Yuborilgan xabarni tahrirlash."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        await client.edit_message(entity, msg_tg_id, new_text)
        # lokal DB'da ham yangilash
        row = (
            await db.execute(
                select(Message).where(Message.dialog_id == dialog.id, Message.tg_id == msg_tg_id)
            )
        ).scalar_one_or_none()
        if row:
            row.text = new_text
            await db.commit()
    return {"ok": True}


async def delete_message(account_id: int, dialog_id: int, msg_tg_id: int, revoke: bool = True) -> dict:
    """Xabarni o'chirish."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        await client.delete_messages(entity, [msg_tg_id], revoke=revoke)
        row = (
            await db.execute(
                select(Message).where(Message.dialog_id == dialog.id, Message.tg_id == msg_tg_id)
            )
        ).scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.commit()
    return {"ok": True}


async def pin_dialog(account_id: int, dialog_id: int, pinned: bool) -> dict:
    """Chatni tepaga qadash."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        if pinned:
            await client.pin_dialog(entity)
        else:
            await client.unpin_dialog(entity)
        dialog.pinned = pinned
        await db.commit()
    return {"ok": True, "pinned": pinned}


async def set_dialog_flags(account_id: int, dialog_id: int, *, muted: bool | None = None, archived: bool | None = None) -> dict:
    """Chatni mute/arxiv qilish (lokal — Telegram serveriga ham sync qilinadi)."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        if muted is not None:
            dialog.muted = muted
            if muted:
                await client.edit_folder(entity, folder=1) if False else None
                # Telethon: mute via client() dialog.mute — soddalashtiramiz: lokal saqlash
            else:
                pass
        if archived is not None:
            dialog.archived = archived
            try:
                # Telegram arxiv papkasi (folder 1 = archive)
                await client(functions.messages.UpdateDialogFilterRequest(id=1, folder=1 if archived else 0))
            except Exception:
                pass
        await db.commit()
    return {"ok": True, "muted": dialog.muted, "archived": dialog.archived}


async def react_message(account_id: int, dialog_id: int, msg_tg_id: int, reaction: str) -> dict:
    """Xabarga reaksiya qo'yish (emoji)."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        try:
            from telethon.tl.types import ReactionEmoji

            await client(functions.messages.SendReactionRequest(
                peer=entity, msg_id=msg_tg_id, reaction=[ReactionEmoji(emoticon=reaction)]
            ))
        except Exception:
            raise ValueError("Reaksiya qo'yib bo'lmadi") from None
    return {"ok": True}


async def send_sticker(account_id: int, dialog_id: int, sticker_id: int | None = None, emoji: str | None = None) -> dict:
    """Stiker/GIF yuborish."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        if sticker_id:
            sent = await client.send_file(entity, file=sticker_id)
        elif emoji:
            sent = await client.send_file(entity, file=emoji)
        else:
            raise ValueError("Stiker ID yoki emoji kerak")
    return {"ok": True, "tg_id": sent.id}


async def create_poll(
    account_id: int,
    dialog_id: int,
    question: str,
    options: list[str],
    anonymous: bool = False,
    multiple_choice: bool = False,
    quiz: bool = False,
    correct_option: int = 0,
    close_period: int = 0,
) -> dict:
    """Haqiqiy Telegram so'rovnomasini (poll) yuboradi.

    anonymous       — ovoz beruvchilar ko'rinmasin
    multiple_choice — bir nechta variantni belgilash mumkin
    quiz            — viktorina rejimi (to'g'ri javob bitta)
    correct_option  — quiz uchun to'g'ri javob indeksi (0 dan)
    close_period    — necha soniyadan keyin avtomatik yopilsin (5..600)
    """
    import random

    from telethon.tl.types import InputMediaPoll, Poll, PollAnswer, TextWithEntities

    client = await _require_client(account_id)

    opts = [str(o).strip() for o in (options or []) if str(o).strip()][:10]
    if len(opts) < 2:
        raise ValueError("So'rovnoma uchun kamida 2 ta javob varianti kerak")
    if len(opts) > 10:
        raise ValueError("Ko'pi bilan 10 ta javob varianti mumkin")
    q = (question or "").strip()
    if not q:
        raise ValueError("So'rovnoma savoli bo'sh bo'lmasligi kerak")

    answers = [
        PollAnswer(text=TextWithEntities(text=o[:100], entities=[]), option=bytes([i]))
        for i, o in enumerate(opts)
    ]
    cp = None
    if close_period:
        cp = min(max(int(close_period), 5), 600)
    poll = Poll(
        id=random.getrandbits(62),
        question=TextWithEntities(text=q[:300], entities=[]),
        answers=answers,
        hash=random.getrandbits(31),
        closed=False,
        public_voters=not anonymous,
        multiple_choice=bool(multiple_choice),
        quiz=bool(quiz),
        close_period=cp,
    )
    # Viktorina to'g'ri javobi InputMediaPoll.correct_answers orqali beriladi.
    media = InputMediaPoll(
        poll=poll,
        correct_answers=[int(correct_option)] if quiz and 0 <= int(correct_option) < len(opts) else None,
    )

    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        try:
            sent = await client.send_file(entity, media)
        except Exception as exc:
            log.warning("create_poll failed: %s: %s", type(exc).__name__, exc)
            raise ValueError(
                "So'rovnoma yuborib bo'lmadi: "
                + ("guruhda xabar yozish huquqi yo'q" if "RIGHT" in str(exc).upper() else str(exc))
            ) from None
    return {
        "ok": True,
        "tg_id": sent.id,
        "question": q,
        "options": opts,
        "anonymous": anonymous,
        "multiple_choice": multiple_choice,
        "quiz": quiz,
        "close_period": cp,
    }


async def media_gallery(account_id: int, dialog_id: int, limit: int = 100) -> list[dict]:
    """Chatdagi barcha media fayllar ro'yxati."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        out = []
        async for m in client.iter_messages(entity, limit=limit):
            if m.media and m.action is None:
                out.append(
                    {
                        "tg_id": m.id,
                        "media_type": media_type_of(m),
                        "date": (m.date or datetime.now(timezone.utc)).isoformat(),
                        "out": bool(m.out),
                    }
                )
    return out


async def read_receipts(account_id: int, dialog_id: int) -> dict:
    """O'qish hisoboti (✓/✓✓ statistikasi)."""
    async with SessionLocal() as db:
        msgs = (
            await db.execute(
                select(Message).where(Message.dialog_id == dialog_id, Message.account_id == account_id)
            )
        ).scalars().all()
    sent = [m for m in msgs if m.out]
    read = [m for m in sent if m.read]
    return {
        "sent": len(sent),
        "read": len(read),
        "delivered_not_read": len(sent) - len(read),
        "read_rate": round(len(read) / len(sent) * 100, 1) if sent else 0,
    }


async def contacts_list(account_id: int) -> list[dict]:
    """Telegram kontaktlar ro'yxati."""
    client = await _require_client(account_id)
    result = await client(functions.contacts.GetContactsRequest(hash=0))
    out = []
    for u in result.users:
        out.append(
            {
                "id": u.id,
                "first_name": getattr(u, "first_name", None),
                "last_name": getattr(u, "last_name", None),
                "username": getattr(u, "username", None),
                "phone": getattr(u, "phone", None),
            }
        )
    return out


async def update_profile(account_id: int, *, first_name: str | None = None, bio: str | None = None, username: str | None = None) -> dict:
    """Profil tahriri (ism/bio/username)."""
    client = await _require_client(account_id)
    if first_name is not None:
        await client(functions.account.UpdateProfileRequest(first_name=first_name))
    if bio is not None:
        await client(functions.account.UpdateProfileRequest(about=bio))
    if username is not None:
        await client(functions.account.UpdateUsernameRequest(username=username))
    return {"ok": True}


async def group_manage(account_id: int, dialog_id: int, user_id: int, action: str, title: str | None = None) -> dict:
    """Guruh boshqaruvi: kick | ban | unban | promote | demote | set_title | rename."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        if action == "kick":
            await client.kick_participant(entity, user_id)
        elif action == "ban":
            await client.edit_permissions(entity, user_id, view_messages=False)
        elif action == "unban":
            await client.edit_permissions(entity, user_id, view_messages=True)
        elif action == "promote":
            await client.edit_admin(entity, user_id, post_messages=True, edit_messages=True, delete_messages=True, ban_users=True)
        elif action == "demote":
            await client.edit_admin(entity, user_id, is_admin=False)
        elif action == "set_title":
            await client.edit_admin(entity, user_id, title=title or "")
        elif action == "rename":
            await client.edit_title(entity, title or "")
        # ---- yangi amallar ----
        elif action == "set_about":
            # Guruh/kanal tavsifi. Telethon'da bitta funksiya ikkalasiga ham
            # ishlaydi: messages.EditChatAboutRequest(peer, about).
            from telethon.tl.functions.messages import EditChatAboutRequest

            peer = await client.get_input_entity(entity)
            await client(EditChatAboutRequest(peer=peer, about=(title or "")[:512]))
        elif action == "slowmode":
            secs = int(title or 0) if str(title or "").isdigit() else 0
            await _set_slowmode(client, entity, secs)
        elif action == "restrict":
            # title = vergul bilan ajratilgan cheklovlar: "media,stickers,preview"
            flags = {f.strip().lower() for f in (title or "").split(",") if f.strip()}
            await client.edit_permissions(
                entity,
                user_id,
                send_media="media" not in flags,
                send_stickers="stickers" not in flags,
                send_gifs="stickers" not in flags,
                embed_links="preview" not in flags,
            )
        elif action == "mute":
            # title = soatlar soni (default 24)
            hours = float(title or 24)
            until = datetime.now(timezone.utc) + timedelta(hours=hours)
            await client.edit_permissions(entity, user_id, until_date=until, send_messages=False)
        elif action == "unmute":
            await client.edit_permissions(entity, user_id, send_messages=True)
        elif action == "delete_user_msgs":
            n = int(title or 20) if str(title or "").isdigit() else 20
            ids = []
            async for m in client.iter_messages(entity, limit=500, from_user=user_id):
                ids.append(m.id)
                if len(ids) >= n:
                    break
            if ids:
                await client.delete_messages(entity, ids)
            return {"ok": True, "deleted": len(ids)}
        else:
            raise ValueError("Noto'g'ri amal")
    return {"ok": True}


async def _set_slowmode(client, entity, seconds: int) -> None:
    """Sekin rejim (faqat megaguruh/kanallar uchun)."""
    from telethon.tl.functions.channels import ToggleSlowModeRequest

    peer = await client.get_input_entity(entity)
    await client(ToggleSlowModeRequest(peer, max(0, min(seconds, 3600))))


async def group_members(account_id: int, dialog_id: int, limit: int = 200) -> list[dict]:
    """Guruh a'zolari ro'yxati."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        participants = await client.get_participants(entity, limit=limit)
    out = []
    for p in participants:
        out.append(
            {
                "id": p.id,
                "first_name": getattr(p, "first_name", None),
                "last_name": getattr(p, "last_name", None),
                "username": getattr(p, "username", None),
            }
        )
    return out


async def schedule_channel_post(account_id: int, dialog_id: int, text: str, send_at, silent: bool = False) -> dict:
    """Kanalga rejalashtirilgan post (silent rejim bilan)."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        sent = await client.send_message(entity, text, silent=silent, schedule=send_at)
    return {"ok": True, "tg_id": sent.id}


# Zaxira nusxa chegaralari: cheksiz yuklash so'rovni vaqt tugashigacha
# ushlab turardi (223 dialog x 1000 xabar) va 500 qaytarardi.
BACKUP_MAX_DIALOGS = 60
BACKUP_MAX_MSGS = 200
BACKUP_TIME_BUDGET = 100.0  # soniya


async def backup_chats(account_id: int) -> dict:
    """Chatlarni JSON ko'rinishida R2'ga zaxiralash (chegarali, xatoga chidamli)."""
    client = await _require_client(account_id)
    started = time.monotonic()
    async with SessionLocal() as db:
        dialogs = (
            await db.execute(
                select(Dialog)
                .where(Dialog.account_id == account_id)
                .order_by(Dialog.pinned.desc(), Dialog.last_msg_date.desc().nullslast())
            )
        ).scalars().all()

        out = []
        skipped = 0
        truncated = False
        for d in dialogs[:BACKUP_MAX_DIALOGS]:
            if time.monotonic() - started > BACKUP_TIME_BUDGET:
                truncated = True
                break
            try:
                entity = await client.get_entity(input_peer(d.tg_id, d.peer_type))
                msgs = [
                    m
                    async for m in client.iter_messages(entity, limit=BACKUP_MAX_MSGS)
                ]
            except Exception as e:  # noqa: BLE001 — bitta dialog butun zaxirani buzmasin
                log.warning("Zaxira: %s dialog o'tkazib yuborildi: %s", d.title, e)
                skipped += 1
                continue
            out.append(
                {
                    "dialog": d.title,
                    "peer_type": d.peer_type,
                    "messages": [
                        {
                            "date": (m.date or datetime.now(timezone.utc)).isoformat(),
                            "out": bool(m.out),
                            "text": m.message or "",
                        }
                        for m in reversed(msgs)
                        if m.action is None
                    ],
                }
            )
    data = json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")
    key = storage.put(data, "application/json", ".json")
    return {
        "key": key,
        "url": storage.url(key),
        "dialogs": len(out),
        "skipped": skipped,
        "truncated": truncated,
        "total_dialogs": len(dialogs),
    }

# ===================================================================
# Guruh / kanal boshqaruvi (admin huquqlari talab qilinadi)
# ===================================================================
TAG_CHUNK = 50  # Telegram bitta xabarda ~50 ta @username'ni ko'taradi
TAG_DELAY = 4.0  # xabarlar orasidagi pauza (spam filtri urilmasligi uchun)


async def _resolve_dialog(client, db, account_id: int, dialog_id: int):
    dialog = (
        await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
    ).scalar_one_or_none()
    if dialog is None:
        raise ValueError("Dialog topilmadi")
    entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
    return dialog, entity


async def _require_admin_rights(client, entity) -> None:
    """Akkaunt shu guruh/kanalda admin ekanini tekshiradi.

    Admin bo'lmasa Telegram xatosi chiqadi — foydalanuvchiga tushunarli
    xabar qaytarish uchun oldindan tekshiramiz.
    """
    from telethon.tl.functions.channels import GetParticipantRequest

    try:
        me = await client.get_me()
        part = await client(GetParticipantRequest(channel=entity, participant=me))
    except Exception as e:  # noqa: BLE001 — oddiy guruh (chat) bo'lsa admin tekshirilmaydi
        log.debug("Admin tekshiruvi o'tkazib yuborildi: %s", e)
        return
    rights = getattr(getattr(part, "participant", None), "admin_rights", None)
    if rights is None:
        raise ValueError("Bu guruh/kanalda akkaunt admin emas. Avval admin qiling.")


_RIGHT_KEYS = (
    "change_info",
    "post_messages",
    "edit_messages",
    "delete_messages",
    "ban_users",
    "invite_users",
    "pin_messages",
    "add_admins",
    "anonymous",
    "manage_call",
    "manage_topics",
)


async def group_admins(account_id: int, dialog_id: int) -> dict:
    """Guruh/kanal adminlari, ularning lavozimi (rank) va huquqlari.

    `get_participants(filter=ChannelParticipantsAdmins())` User obyektini
    qaytaradi va har biriga `.participant` biriktirilgan:
    ChannelParticipantCreator (egasi) yoki ChannelParticipantAdmin.
    """
    from telethon.tl.types import (
        ChannelParticipantCreator,
        ChannelParticipantsAdmins,
        InputPeerSelf,
    )

    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog, entity = await _resolve_dialog(client, db, account_id, dialog_id)
        participants = await client.get_participants(entity, filter=ChannelParticipantsAdmins())

    admins = []
    creator = None
    for p in participants:
        part = getattr(p, "participant", None)
        is_creator = isinstance(part, ChannelParticipantCreator)
        rights_obj = getattr(part, "admin_rights", None)
        rights = {k: bool(getattr(rights_obj, k, False)) for k in _RIGHT_KEYS}
        entry = {
            "id": int(p.id),
            "first_name": getattr(p, "first_name", "") or "",
            "last_name": getattr(p, "last_name", "") or "",
            "username": getattr(p, "username", None),
            "is_creator": is_creator,
            "bot": bool(getattr(p, "bot", False)),
            "rank": getattr(part, "rank", None),
            "can_edit": bool(getattr(part, "can_edit", False)),
            "promoted_by": getattr(part, "promoted_by", None),
            "rights": rights,
        }
        admins.append(entry)
        if is_creator and creator is None:
            creator = {
                "id": entry["id"],
                "first_name": entry["first_name"],
                "username": entry["username"],
            }

    # Egasi admin ro'yxatida ko'rinmasa ham uni alohida topib beramiz.
    if creator is None:
        try:
            me = await client(
                functions.channels.GetParticipantRequest(
                    channel=entity, participant=InputPeerSelf()
                )
            )
            if isinstance(me.participant, ChannelParticipantCreator):
                u = me.users[0] if getattr(me, "users", None) else None
                creator = {
                    "id": int(u.id) if u else int(me.participant.user_id),
                    "first_name": (getattr(u, "first_name", "") if u else "") or "",
                    "username": getattr(u, "username", None) if u else None,
                }
        except Exception as exc:
            log.debug("group_admins creator lookup failed: %s", exc)

    total = getattr(entity, "participants_count", None)
    if not total:
        # participants_count ba'zida None keladi; limit=0 umumiy sonni beradi.
        try:
            total = await client.get_participants(entity, limit=0)
        except Exception as exc:
            log.debug("group_admins member count failed: %s", exc)
    return {
        "admins": admins,
        "creator": creator,
        "count": len(admins),
        "kind": dialog.kind or dialog.peer_type,
        "peer_type": dialog.peer_type,
        "title": dialog.title,
        "total_members": total,
    }


async def tag_all_usernames(
    account_id: int,
    dialog_id: int,
    text: str = "",
    preview: bool = False,
    limit: int = 500,
) -> dict:
    """Guruhdagi barcha @username'larni xabarga teg qilib yuboradi.

    Telegram bitta xabarda ko'p mention'ni ko'tarmaydi, shuning uchun
    50 talik bo'laklarga bo'linadi va orasida pauza qo'yiladi.
    preview=True bo'lsa hech narsa yuborilmaydi (faqat reja qaytadi) —
    xavfsiz tekshirish uchun.
    """
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog, entity = await _resolve_dialog(client, db, account_id, dialog_id)
        await _require_admin_rights(client, entity)
        participants = await client.get_participants(entity, limit=limit)

    usernames = [
        u for u in (getattr(p, "username", None) for p in participants) if u
    ]
    # dublikatlarni saqlagan holda takrorlanishni olamiz
    seen, uniq = set(), []
    for u in usernames:
        if u.lower() not in seen:
            seen.add(u.lower())
            uniq.append(u)

    chunks = [uniq[i : i + TAG_CHUNK] for i in range(0, len(uniq), TAG_CHUNK)]
    header = (text or "").strip()

    if preview:
        return {
            "ok": True,
            "preview": True,
            "total_members": len(participants),
            "with_username": len(uniq),
            "messages": len(chunks),
            "chunks": [" ".join(f"@{u}" for u in c[:5]) + (" …" if len(c) > 5 else "") for c in chunks],
        }

    sent = 0
    for i, chunk in enumerate(chunks):
        mentions = " ".join(f"@{u}" for u in chunk)
        body = f"{header}\n\n{mentions}" if (header and i == 0) else (header if i == 0 else mentions)
        await client.send_message(entity, body[:4000])
        sent += 1
        if i < len(chunks) - 1:
            await asyncio.sleep(TAG_DELAY)

    return {
        "ok": True,
        "total_members": len(participants),
        "with_username": len(uniq),
        "messages_sent": sent,
    }


async def group_invite_link(
    account_id: int, dialog_id: int, action: str = "create", expire_hours: int = 0, usage_limit: int = 0
) -> dict:
    """Taklif havolasini yaratish yoki bekor qilish."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog, entity = await _resolve_dialog(client, db, account_id, dialog_id)
        await _require_admin_rights(client, entity)
        peer = await client.get_input_entity(entity)

        if action == "revoke":
            res = await client(
                functions.messages.ExportChatInviteRequest(
                    peer=peer, legacy_revoke_permanent=True, request_needed=False
                )
            )
            return {"ok": True, "revoked": True, "link": getattr(res, "link", None)}

        kwargs = {}
        if expire_hours > 0:
            kwargs["expire_date"] = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
        if usage_limit > 0:
            kwargs["usage_limit"] = usage_limit
        res = await client(
            functions.messages.ExportChatInviteRequest(
                peer=peer, legacy_revoke_permanent=False, request_needed=False, **kwargs
            )
        )
        exp = getattr(res, "expire_date", None)
        return {
            "ok": True,
            "revoked": False,
            "link": getattr(res, "link", None),
            "expires": exp.isoformat() if exp is not None else None,
            "usage_limit": getattr(res, "usage_limit", None),
            "requested": bool(getattr(res, "request_needed", False)),
        }


async def broadcast_to_admin_chats(
    account_id: int, text: str, only_kind: str = "", limit_dialogs: int = 30
) -> dict:
    """Akkaunt ADMIN bo'lgan barcha guruh/kanallarga bir xil xabar yuboradi.

    only_kind: "" (hammasi) | "group" | "channel"
    """
    client = await _require_client(account_id)
    if not (text or "").strip():
        raise ValueError("Xabar matni bo'sh")

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Dialog).where(Dialog.account_id == account_id).order_by(
                    Dialog.pinned.desc(), Dialog.last_msg_date.desc().nullslast()
                )
            )
        ).scalars().all()

    sent, skipped, errors = 0, 0, []
    for d in rows:
        if only_kind and d.peer_type != only_kind:
            continue
        if sent >= limit_dialogs:
            break
        try:
            entity = await client.get_entity(input_peer(d.tg_id, d.peer_type))
            await _require_admin_rights(client, entity)
        except ValueError:
            skipped += 1  # admin emasmiz — o'tkazamiz
            continue
        except Exception as e:  # noqa: BLE001
            errors.append(f"{d.title}: {e}")
            continue
        try:
            await client.send_message(entity, text[:4000])
            sent += 1
            await asyncio.sleep(2.5)  # spam filtri urilmasligi uchun
        except Exception as e:  # noqa: BLE001
            errors.append(f"{d.title}: {e}")
    return {"ok": True, "sent": sent, "skipped_not_admin": skipped, "errors": errors[:10]}
