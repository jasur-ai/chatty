"""Avto-javob (auto-reply) moduli.

Eslatma: ilgari bu yerda "so'kinish filtri" (ogohlantirish/bloklash) bo'lgan —
u foydalanuvchi so'rovi bilan butkul olib tashlandi. Endi faqat avto-javob qoladi.

Avto-javob:
  - Yoqilgan bo'lsa, kiruvchi xabarga avtomatik javob yuboriladi.
  - "Belgilangan" odamlar ro'yxati bo'lsa, ularga auto_reply_selected_text (yoki
    asosiy matn) yuboriladi; ro'yxatga kirmaganlarga asosiy auto_reply_text yuboriladi.
"""
import logging
from datetime import datetime

from sqlalchemy import select

from ..db import AppUser, AutoReplyTarget, Dialog, SessionLocal

log = logging.getLogger("chatty.filter")

# Avto-javob uchun tayyor taklifiy matnlar (frontend ham shuni ishlatadi)
SUGGESTED_REPLIES = [
    "Hozir bandman, keyinroq yozing.",
    "Salom, nima bilan murojaat qilyapsiz?",
    "Xabaringizni oldim, tez orada javob beraman.",
    "Kechirasiz, hozir javob bera olmayman. Iltimos, biroz kuting.",
    "Assalomu alaykum, xush kelibsiz. Qanday yordam bera olaman?",
]


async def apply_incoming(client, account_id: int, dialog: Dialog, msg) -> bool:
    """Kiruvchi xabarga avto-javobni qo'llaydi.

    Qaytadi: xabar yashirilishi kerak bo'lsa True. (Hozir hech narsa yashirilmaydi —
    doim False; so'kinish filtri olib tashlangan.)
    """
    if msg.out:
        return False

    from .sync import input_peer  # noqa: PLC0415

    sender_id = msg.sender_id
    if sender_id is None and dialog.peer_type == "user":
        sender_id = dialog.tg_id
    text = msg.message or ""
    peer = input_peer(dialog.tg_id, dialog.peer_type)

    # ---- avto-javob (faqat private user chatlar) ----
    if sender_id and dialog.peer_type == "user":
        reply_text = await should_auto_reply(account_id, sender_id)
        if reply_text:
            try:
                await client.send_message(peer, reply_text)
            except Exception as e:  # noqa: BLE001
                log.warning("Avto-javob yuborilmadi: %s", e)
        else:
            # VIP uchun AI kontekstli avto-javob (avto-javob yoqilgan bo'lsa)
            async with SessionLocal() as db:
                app_user = (
                    await db.execute(select(AppUser).where(AppUser.account_id == account_id))
                ).scalar_one_or_none()
            if app_user and app_user.auto_reply_enabled and app_user.is_vip and text:
                from ..lotus import lotus  # noqa: PLC0415

                ai = await lotus.ai_reply_text(text, account_id)
                if ai:
                    try:
                        await client.send_message(peer, ai)
                    except Exception as e:  # noqa: BLE001
                        log.warning("AI avto-javob yuborilmadi: %s", e)

    return False


async def should_auto_reply(account_id: int, user_tg_id: int) -> str | None:
    """Avto-javob matnini qaytaradi (kerak bo'lmasa None). Jadvalni hisobga oladi."""
    async with SessionLocal() as db:
        app_user = (
            await db.execute(select(AppUser).where(AppUser.account_id == account_id))
        ).scalar_one_or_none()
        if app_user is None or not app_user.auto_reply_enabled:
            return None
        default_text = app_user.auto_reply_text or SUGGESTED_REPLIES[0]

        # Jadval oynasini tekshirish (masalan "09:00" - "18:00")
        if app_user.auto_reply_from and app_user.auto_reply_to:
            now = datetime.now().time()
            frm = _parse_hhmm(app_user.auto_reply_from)
            to = _parse_hhmm(app_user.auto_reply_to)
            if frm and to and not (frm <= now <= to):
                return None

        targets = (
            await db.execute(
                select(AutoReplyTarget).where(AutoReplyTarget.account_id == account_id)
            )
        ).scalars().all()
        selected_ids = {t.tg_user_id for t in targets}

        # Belgilangan odamlar ro'yxati bo'sh bo'lsa — hammaga asosiy matn.
        if not selected_ids:
            return default_text
        # Ro'yxat bor va yozuvchi ro'yxatda bo'lsa — belgilangan matn.
        if user_tg_id in selected_ids:
            return app_user.auto_reply_selected_text or default_text
        # Ro'yxat bor, lekin yozuvchi ro'yxatda yo'q — ham asosiy matn.
        return default_text


def _parse_hhmm(s: str):
    try:
        from datetime import time  # noqa: PLC0415

        h, m = s.strip().split(":")
        return time(int(h), int(m))
    except Exception:  # noqa: BLE001
        return None
