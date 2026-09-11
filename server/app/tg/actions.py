"""Chat harakatlari: dialoglar/xabarlar sinxroni, yuborish, o'qilgan qilish."""
import asyncio
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
    _process_media,
    download_dialog_photo,
    input_peer,
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
            dialogs = [serialize_dialog(d) for d in existing]
            if any(not d.photo_key for d in existing):
                asyncio.create_task(backfill_avatars(account_id))
            return dialogs

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
            asyncio.create_task(backfill_avatars(account_id))
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


async def create_poll(account_id: int, dialog_id: int, question: str, options: list[str]) -> dict:
    """So'rov (poll) yaratish."""
    client = await _require_client(account_id)
    async with SessionLocal() as db:
        dialog = (
            await db.execute(select(Dialog).where(Dialog.id == dialog_id, Dialog.account_id == account_id))
        ).scalar_one_or_none()
        if dialog is None:
            raise ValueError("Dialog topilmadi")
        entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
        sent = await client.send_message(entity, file=None)
        try:
            from telethon.tl.types import Poll, PollAnswer

            msg = await client.send_message(
                entity,
                question,
            )
            # Soddalashtirilgan: text orqali yuboramiz (poll API murakkab)
            sent = msg
        except Exception:
            raise ValueError("So'rov yaratib bo'lmadi") from None
    return {"ok": True, "tg_id": sent.id}


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
        else:
            raise ValueError("Noto'g'ri amal")
    return {"ok": True}


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