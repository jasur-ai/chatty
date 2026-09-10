"""So'kinish filtri va avto-javob.

So'kinish filtri qoidalari (spec bo'yicha):
  - Private chat: har safar ogohlantirish yuboriladi; 3-marta -> odam bloklanadi.
  - Guruh/chat: faqat ogohlantirish yuboriladi; 3+ marta oshgach, o'sha odamning
    keyingi xabarlari chatda ko'rinmaydigan (hidden) qilinadi.

Avto-javob:
  - Yoqilgan bo'lsa, kiruvchi xabarga avtomatik javob yuboriladi.
  - "Belgilangan" odamlar ro'yxati bo'lsa, ularga auto_reply_selected_text (yoki
    asosiy matn) yuboriladi; ro'yxatga kirmaganlarga asosiy auto_reply_text yuboriladi.
"""
import logging
import re
from datetime import datetime

from sqlalchemy import select

from ..db import AppUser, AutoReplyTarget, Dialog, SessionLocal, WarnState

log = logging.getLogger("chatty.filter")

# So'kinish kalit so'zlari (uz/ru). Lug'atni osongina kengaytirish mumkin.
BANNED_WORDS = [
    "ahmoq", "jinni", "tentak", "so'k", "sok", "blu", "blyad", "blya",
    "sharmanda", "iflos", "ho'kiz", "hukiz", "eski", "qo'pol", "qopol",
    "suka", "сука", "бля", "блять", "дурак", "тупой", "идиот", "дебил",
    "ебан", "хуй", "хуе", "пизд", "нахуй", "аху", "оху", "мудак", "говно",
    "fuck", "shit", "asshole", "bitch", "bastard", "stupid", "idiot",
]

# Avto-javob uchun tayyor taklifiy matnlar (frontend ham shuni ishlatadi)
SUGGESTED_REPLIES = [
    "Hozir bandman, keyinroq yozing.",
    "Salom, nima bilan murojaat qilyapsiz?",
    "Xabaringizni oldim, tez orada javob beraman.",
    "Kechirasiz, hozir javob bera olmayman. Iltimos, biroz kuting.",
    "Assalomu alaykum, xush kelibsiz. Qanday yordam bera olaman?",
]


def contains_profanity(text: str) -> str | None:
    """Matndagi birinchi so'kinish kalit so'zini qaytaradi (topilmasa None)."""
    if not text:
        return None
    low = text.lower()
    for w in BANNED_WORDS:
        # So'z chegarasi bo'yicha qidirish (so'k so'z 'so'k' bilan mos kelmasin)
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
            return w
    return None


async def _get_warn(db, account_id: int, dialog: Dialog, user_tg_id: int) -> WarnState:
    row = (
        await db.execute(
            select(WarnState).where(
                WarnState.account_id == account_id,
                WarnState.dialog_id == dialog.tg_id,
                WarnState.user_tg_id == user_tg_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = WarnState(account_id=account_id, dialog_id=dialog.tg_id, user_tg_id=user_tg_id, warns=0)
        db.add(row)
        await db.flush()
    return row


async def check_profanity(account_id: int, dialog: Dialog, user_tg_id: int, text: str) -> dict | None:
    """So'kinishni tekshiradi. Harakat kerak bo'lsa dict qaytaradi, aks holda None.

    Qaytadigan dict: {"action": "warn"|"block"|"hide", "warns": N}
    """
    bad = contains_profanity(text)
    if bad is None:
        return None

    async with SessionLocal() as db:
        warn = await _get_warn(db, account_id, dialog, user_tg_id)
        warn.warns += 1
        await db.commit()
        warns = warn.warns
        is_group = dialog.peer_type in ("chat", "channel")

    if warns >= 3:
        if is_group:
            # Guruhda bloklanmaydi — xabarlar yashirin qilinadi
            return {"action": "hide", "warns": warns}
        return {"action": "block", "warns": warns}
    return {"action": "warn", "warns": warns}


async def mark_blocked(account_id: int, dialog: Dialog, user_tg_id: int) -> None:
    async with SessionLocal() as db:
        warn = (
            await db.execute(
                select(WarnState).where(
                    WarnState.account_id == account_id,
                    WarnState.dialog_id == dialog.tg_id,
                    WarnState.user_tg_id == user_tg_id,
                )
            )
        ).scalar_one_or_none()
        if warn is not None:
            warn.blocked = True
            await db.commit()


async def is_blocked(account_id: int, dialog: Dialog, user_tg_id: int) -> bool:
    async with SessionLocal() as db:
        warn = (
            await db.execute(
                select(WarnState).where(
                    WarnState.account_id == account_id,
                    WarnState.dialog_id == dialog.tg_id,
                    WarnState.user_tg_id == user_tg_id,
                )
            )
        ).scalar_one_or_none()
        return bool(warn and warn.blocked)


async def apply_incoming(client, account_id: int, dialog: Dialog, msg) -> bool:
    """Kiruvchi xabarga so'kinish filtri va avto-javobni qo'llaydi.

    Qaytadi: xabar yashirilishi kerak bo'lsa True (guruhda 3+ so'kinish).
    """
    if msg.out:
        return False

    from ..db import SessionLocal  # noqa: PLC0415
    from .sync import input_peer  # noqa: PLC0415

    sender_id = msg.sender_id
    if sender_id is None and dialog.peer_type == "user":
        sender_id = dialog.tg_id
    text = msg.message or ""
    peer = input_peer(dialog.tg_id, dialog.peer_type)

    # ---- so'kinish filtri ----
    if sender_id and text:
        result = await check_profanity(account_id, dialog, sender_id, text)
        if result:
            action = result["action"]
            warns = result["warns"]
            if action == "hide":
                # Guruhda 3+ marta — xabarlarni yashirish (bloklanmaydi)
                await client.send_message(
                    peer,
                    f"Ogohlantirish ({warns}/3): bu foydalanuvchining xabarlari chatda ko'rsatilmaydi.",
                )
                return True
            if action == "block":
                from telethon import functions

                try:
                    await client(functions.contacts.BlockRequest(id=peer))
                except Exception as e:  # noqa: BLE001
                    log.warning("Bloklashda xato: %s", e)
                await mark_blocked(account_id, dialog, sender_id)
                await client.send_message(
                    peer, "Siz qoidalarni bir necha bor buzdingiz va bloklandingiz."
                )
                return False
            # warn (1-2 marta)
            await client.send_message(
                peer, f"Ogohlantirish ({warns}/3): so'kinish qabul qilinmaydi."
            )
            return False

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
            from ..db import AppUser  # noqa: PLC0415

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
