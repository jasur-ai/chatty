"""Telethon update handlerlari: xabarlar va o'qilgan holatlar → DB + WebSocket."""
import asyncio
import logging

from sqlalchemy import select, update as sa_update
from telethon import events

from ..config import settings
from ..db import Account, AppUser, Dialog, Message, SessionLocal
from ..notify import media_brief, notifier
from ..security import decrypt_session
from ..ws import ws_manager
from .sync import serialize_dialog, serialize_message, update_dialog_last, upsert_dialog, upsert_message

log = logging.getLogger("chatty.events")


async def on_new_message(event: events.NewMessage.Event, account_id: int) -> None:
    msg = event.message
    if msg is None:
        return
    if msg.action is not None:  # servis xabarlar (qo'shildi, chiqdi ...) — hozircha skip
        return

    async with SessionLocal() as db:
        try:
            chat = await event.get_chat()
        except Exception:
            return
        dialog = await upsert_dialog(db, account_id, chat)
        is_out = bool(msg.out)
        if not is_out:
            dialog.unread_count += 1
        try:
            row = await upsert_message(db, event.client, account_id, dialog, msg)
        except Exception as e:
            log.warning("Xabarni saqlashda xato: %s", e)
            return
        await update_dialog_last(db, dialog, msg, is_out)
        await db.commit()

        payload = {
            "type": "message",
            "dialog": serialize_dialog(dialog),
            "message": serialize_message(row),
        }
        await ws_manager.broadcast(account_id, payload)

        # Push-xabarnoma: app ochiq bo'lmasa va chat USER bo'lsa
        # (kanal/guruh xabarlari faqat app ichida ko'rinadi — spec bo'yicha)
        if not is_out and dialog.peer_type == "user":
            connected = ws_manager.connections.get(account_id)
            if not connected:
                app_user = (
                    await db.execute(select(AppUser).where(AppUser.account_id == account_id))
                ).scalar_one_or_none()
                owner_chat_id = app_user.tg_user_id if app_user else None
                if owner_chat_id:
                    brief = media_brief(msg)
                    notif_text = (
                        brief
                        or (msg.message or "")[:200]
                        or "Yangi xabar"
                    )
                    asyncio.create_task(
                        notifier.send_notification(
                            owner_chat_id,
                            notif_text,
                            button_url=settings.bot_reply_url or None,
                        )
                    )


async def on_message_read(event: events.MessageRead.Event, account_id: int) -> None:
    """Odamlar sizning yuborgan xabaringizni o'qiganda (✓✓) — outbox=True event'lar keladi."""
    if not event.outbox:
        return  # biz o'qidik — bu haqida app allaqachon biladi
    try:
        peer_id = event.chat_id
    except Exception:
        return

    async with SessionLocal() as db:
        dialog = (
            await db.execute(
                select(Dialog).where(Dialog.account_id == account_id, Dialog.tg_id == peer_id)
            )
        ).scalar_one_or_none()
        if dialog is None:
            return
        await db.execute(
            sa_update(Message)
            .where(
                Message.dialog_id == dialog.id,
                Message.out.is_(True),
                Message.tg_id <= event.max_id,
                Message.read.is_(False),
            )
            .values(read=True)
        )
        await db.commit()
        await ws_manager.broadcast(
            account_id,
            {
                "type": "read_outbox",
                "dialog_id": dialog.id,
                "max_tg_id": event.max_id,
            },
        )