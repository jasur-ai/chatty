"""Telegram login flow: telefon → kod → 2FA parol."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from ..config import settings
from ..db import Account, AppUser, SessionLocal
from ..security import create_token, encrypt_session
from .manager import manager
from .sync import serialize_account

log = logging.getLogger("chatty.auth")

PINK_MODE_USER_ID = 8442078631  # bu admin ulanganda tizim pink rejimga o'tadi

# Anti-spam: Telegram kod so'rovlarini tez-tez qilinsa bostiradi
CODE_MIN_INTERVAL = timedelta(seconds=30)  # ikki so'rov orasidagi minimal vaqt
CODE_MAX_ATTEMPTS_PER_HOUR = 5  # soatiga maksimal urinish


def _check_code_limits(acc: Account) -> None:
    now = datetime.now(timezone.utc)
    last = acc.last_code_at
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        # Bir soat o'tgan bo'lsa, urinishlar hisobini tozalaymiz
        if now - last > timedelta(hours=1):
            acc.code_attempts = 0
        elif now - last < CODE_MIN_INTERVAL:
            raise ValueError("Kod hozirgina yuborildi. 30 soniya kuting, qayta urinmang — aks holda Telegram bloklaydi.")
    if acc.code_attempts >= CODE_MAX_ATTEMPTS_PER_HOUR:
        raise ValueError("Juda ko'p urinish — Telegram kod yuborishni vaqtincha to'xtatdi. 30-60 daqiqa kuting.")


async def _get_or_create_account(phone: str, api_id: int | None, api_hash: str | None) -> Account:
    async with SessionLocal() as db:
        acc = (
            await db.execute(select(Account).where(Account.phone == phone))
        ).scalar_one_or_none()
        if acc is None:
            acc = Account(phone=phone, api_id=api_id, api_hash=api_hash, auth_step="none")
            db.add(acc)
            await db.commit()
            await db.refresh(acc)
        return acc


async def start_login(phone: str, api_id: int | None = None, api_hash: str | None = None) -> dict:
    """Kod yuboradi. Qaytadi: {"step": "code"}"""
    api_id = api_id or settings.tg_api_id
    api_hash = api_hash or settings.tg_api_hash
    if not api_id or not api_hash:
        raise ValueError("TG_API_ID va TG_API_HASH sozlanishi shart (my.telegram.org)")

    acc = await _get_or_create_account(phone, api_id, api_hash)
    _check_code_limits(acc)

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except errors.FloodWaitError as e:
        await client.disconnect()
        raise ValueError(f"Juda ko'p urinish. {e.seconds} soniya kuting") from e
    except errors.PhoneNumberInvalidError as e:
        await client.disconnect()
        raise ValueError("Telefon raqam noto'g'ri") from e
    except Exception as e:
        await client.disconnect()
        log.error("Kod yuborishda xato: %s", e)
        raise ValueError("Kod yuborishda xato yuz berdi") from e

    manager.pending[phone] = client

    # Qaysi usul tanlanganini log'ga yozamiz (SMS/app/qo'ng'iroq) — diagnostika uchun
    log.info(
        "Kod so'rovi: %s -> %s (code_hash=%s...)",
        phone,
        type(sent.type).__name__,
        sent.phone_code_hash[:8],
    )

    async with SessionLocal() as db:
        acc = (
            await db.execute(select(Account).where(Account.phone == phone))
        ).scalar_one()
        acc.auth_step = "code_sent"
        acc.phone_code_hash = sent.phone_code_hash
        acc.last_code_at = datetime.now(timezone.utc)
        acc.code_attempts += 1
        await db.commit()

    return {"step": "code"}


async def verify_code(phone: str, code: str) -> dict:
    """Kodni tekshiradi. 2FA kerak bo'lsa {"step":"password"} qaytaradi."""
    client = manager.pending.get(phone)
    if client is None:
        raise ValueError("Avval kod yuborilishi kerak")

    async with SessionLocal() as db:
        acc = (
            await db.execute(select(Account).where(Account.phone == phone))
        ).scalar_one()

    try:
        me = await client.sign_in(phone=phone, code=code, phone_code_hash=acc.phone_code_hash)
    except errors.SessionPasswordNeededError:
        async with SessionLocal() as db:
            acc = (
                await db.execute(select(Account).where(Account.phone == phone))
            ).scalar_one()
            acc.auth_step = "awaiting_2fa"
            await db.commit()
        return {"step": "password"}
    except errors.PhoneCodeInvalidError as e:
        raise ValueError("Kod noto'g'ri") from e
    except errors.PhoneCodeExpiredError as e:
        raise ValueError("Kod muddati tugagan, qayta yuboring") from e
    except errors.FloodWaitError as e:
        raise ValueError(f"Juda ko'p urinish. {e.seconds} soniya kuting") from e

    return await _finalize(phone, client, me)


async def submit_password(phone: str, password: str) -> dict:
    client = manager.pending.get(phone)
    if client is None:
        raise ValueError("Avval kod yuborilishi kerak")
    try:
        me = await client.sign_in(phone=phone, password=password)
    except errors.PasswordHashInvalidError as e:
        raise ValueError("Parol noto'g'ri") from e
    except errors.FloodWaitError as e:
        raise ValueError(f"Juda ko'p urinish. {e.seconds} soniya kuting") from e
    return await _finalize(phone, client, me)


async def _finalize(phone: str, client: TelegramClient, me) -> dict:
    raw = client.session.save()
    enc = encrypt_session(raw)

    async with SessionLocal() as db:
        acc = (
            await db.execute(select(Account).where(Account.phone == phone))
        ).scalar_one()
        acc.session_enc = enc
        acc.auth_step = "ready"
        acc.first_name = getattr(me, "first_name", None)
        acc.username = getattr(me, "username", None)
        await db.flush()

        app_user = (
            await db.execute(select(AppUser).where(AppUser.account_id == acc.id))
        ).scalar_one_or_none()
        tg_id = me.id
        is_owner = tg_id == settings.owner_id
        is_admin = tg_id in settings.admin_ids or is_owner
        theme = "pink" if tg_id == PINK_MODE_USER_ID else "default"
        if app_user is None:
            app_user = AppUser(
                account_id=acc.id,
                tg_user_id=tg_id,
                is_owner=is_owner,
                is_admin=is_admin,
                theme=theme,
            )
            db.add(app_user)
        else:
            app_user.tg_user_id = tg_id
            app_user.is_owner = is_owner
            app_user.is_admin = is_admin
            app_user.theme = theme
        await db.commit()
        await db.refresh(acc)
        await db.refresh(app_user)

    # Login uchun ishlatilgan clientni yopamiz, sessiyadan toza client ochamiz
    await client.disconnect()
    manager.pending.pop(phone, None)
    await manager.start_account(acc)

    return {
        "token": create_token(acc.id),
        "account": serialize_account(acc),
        "app_user": {
            "is_owner": app_user.is_owner,
            "is_admin": app_user.is_admin,
            "is_vip": app_user.is_vip,
            "theme": app_user.theme,
        },
    }