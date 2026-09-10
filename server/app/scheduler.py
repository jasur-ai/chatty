"""Fon vazifalari: Lotus eslatmalari va Admin AI davriy hisobotlari.

Admin AI hisobotlari sozlanadigan oraliqda ishlaydi (default 2 soat;
1/2/4/6/8 soat). Har bir hisobot barcha akkauntlar bo'yicha qisqacha statistika
beradi: yangi xabarlar, dialoglar, faol akkauntlar va h.k.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import settings
from .db import (
    Account,
    AdminReport,
    AppUser,
    AutoDeleteRule,
    AutoForwardRule,
    Dialog,
    Message,
    Reminder,
    ScheduledMessage,
    SessionLocal,
)
from .notify import notifier
from .tg.manager import manager
from .tg.sync import input_peer

log = logging.getLogger("chatty.scheduler")

REPORT_INTERVALS = {1, 2, 4, 6, 8}
DEFAULT_INTERVAL_HOURS = 2


# ---------------- eslatmalar ----------------
async def add_reminder(text: str, due_at: datetime, account_id: int | None = None) -> int:
    async with SessionLocal() as db:
        r = Reminder(account_id=account_id, text=text, due_at=due_at)
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return r.id


async def list_reminders_text(language: str) -> str:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at)
            )
        ).scalars().all()
    if not rows:
        return {
            "uz": "Hech qanday faol eslatma yo'q.",
            "ru": "Нет активных напоминаний.",
            "en": "No active reminders.",
        }[language]
    lines = {
        "uz": "Eslatmalaringiz:\n",
        "ru": "Ваши напоминания:\n",
        "en": "Your reminders:\n",
    }[language]
    for r in rows:
        t = r.due_at.strftime("%d.%m %H:%M")
        lines += f"- {r.text} ({t})\n"
    return lines.strip()


async def _due_reminders() -> None:
    """Muddati kelgan eslatmalarni egasiga yuboradi."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Reminder).where(Reminder.done.is_(False), Reminder.due_at <= now)
            )
        ).scalars().all()
    for r in rows:
        async with SessionLocal() as db:
            acc_id = r.account_id
            if acc_id:
                app_user = (
                    await db.execute(select(AppUser).where(AppUser.account_id == acc_id))
                ).scalar_one_or_none()
                owner = app_user.tg_user_id if app_user else None
            else:
                # global eslatma -> owner'ga
                owner = settings.owner_id
            if owner:
                await notifier.send_notification(owner, f"Eslatma: {r.text}")
            r.done = True
            await db.commit()


# ---------------- admin hisobot ----------------
async def build_report_text(language: str = "uz") -> str:
    """Barcha akkauntlar bo'yicha qisqacha hisobot matni."""
    async with SessionLocal() as db:
        accounts = (await db.execute(select(Account))).scalars().all()
        total_dialogs = 0
        total_msgs = 0
        lines = []
        for a in accounts:
            dialogs = (
                await db.execute(select(Dialog).where(Dialog.account_id == a.id))
            ).scalars().all()
            msgs = (
                await db.execute(select(Message).where(Message.account_id == a.id))
            ).scalars().all()
            unread = sum(d.unread_count for d in dialogs)
            total_dialogs += len(dialogs)
            total_msgs += len(msgs)
            name = a.bot_name or a.first_name or a.phone
            lines.append(f"- {name}: {len(dialogs)} chat, {len(msgs)} xabar, {unread} o'qilmagan")
        head = f"Hisobot ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC)\n"
        head += f"Ulangan akkauntlar: {len(accounts)}\nJami chatlar: {total_dialogs}, jami xabarlar: {total_msgs}\n"
        return (head + "\n".join(lines)).strip()


async def _process_scheduled() -> None:
    """Muddati kelgan rejalashtirilgan xabarlarni yuboradi."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(ScheduledMessage).where(ScheduledMessage.sent.is_(False), ScheduledMessage.send_at <= now)
            )
        ).scalars().all()
    for s in rows:
        client = manager.get(s.account_id)
        if client is None:
            continue
        async with SessionLocal() as db:
            dialog = (
                await db.execute(select(Dialog).where(Dialog.id == s.dialog_id))
            ).scalar_one_or_none()
            if dialog is None:
                continue
            entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
            try:
                if s.media_key:
                    from ..storage import storage  # noqa: PLC0415

                    data, _ = storage.get(s.media_key)
                    import tempfile
                    from pathlib import Path

                    ext = Path(s.media_key).suffix or ".bin"
                    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    try:
                        tmp.write(data)
                        tmp.close()
                        await client.send_file(entity, tmp.name, caption=s.text or None)
                    finally:
                        Path(tmp.name).unlink(missing_ok=True)
                else:
                    await client.send_message(entity, s.text)
                s.sent = True
                await db.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("Rejalashtirilgan xabar yuborilmadi: %s", e)


async def _process_auto_delete() -> None:
    """Avto-o'chirish qoidalari: yuborilgan xabarlarni TTL'dan keyin o'chirish."""
    async with SessionLocal() as db:
        rules = (await db.execute(select(AutoDeleteRule).where(AutoDeleteRule.ttl_seconds > 0))).scalars().all()
    for r in rules:
        client = manager.get(r.account_id)
        if client is None:
            continue
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=r.ttl_seconds)
        async with SessionLocal() as db:
            msgs = (
                await db.execute(
                    select(Message).where(
                        Message.account_id == r.account_id,
                        Message.out.is_(True),
                        Message.date < cutoff,
                    )
                )
            ).scalars().all()
            for m in msgs:
                dialog = (
                    await db.execute(select(Dialog).where(Dialog.id == m.dialog_id))
                ).scalar_one_or_none()
                if dialog is None:
                    continue
                try:
                    entity = await client.get_entity(input_peer(dialog.tg_id, dialog.peer_type))
                    await client.delete_messages(entity, [m.tg_id])
                except Exception:  # noqa: BLE001
                    continue


async def _run_report() -> None:
    body = await build_report_text()
    async with SessionLocal() as db:
        db.add(AdminReport(body=body))
        await db.commit()
    # Owner va adminlarga yuborish
    async with SessionLocal() as db:
        admins = (
            await db.execute(
                select(AppUser).where((AppUser.is_owner.is_(True)) | (AppUser.is_admin.is_(True)))
            )
        ).scalars().all()
    for a in admins:
        if a.tg_user_id:
            await notifier.send_notification(a.tg_user_id, body)
    log.info("Admin hisobot yuborildi")


def report_interval_hours() -> int:
    try:
        return int(getattr(settings, "report_interval_hours", DEFAULT_INTERVAL_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS


class Scheduler:
    """Har X soniyada bir vazifalarni bajaradigan oddiy loop."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        last_report = datetime.now(timezone.utc)
        while True:
            try:
                await _due_reminders()
                await _process_scheduled()
                await _process_auto_delete()
                now = datetime.now(timezone.utc)
                interval = timedelta(hours=report_interval_hours())
                if now - last_report >= interval:
                    await _run_report()
                    last_report = now
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("Scheduler xatosi: %s", e)
            await asyncio.sleep(30)


scheduler = Scheduler()
