"""Login API: start (kod yuborish), verify (kod), password (2FA), silent (Telegram)."""
import hashlib
import hmac
import json as _json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import settings
from ..db import Account, AppUser, SessionLocal
from ..security import create_token
from ..tg.auth import start_login, submit_password, verify_code
from ..tg.sync import serialize_account

router = APIRouter(prefix="/api/auth", tags=["auth"])


class StartIn(BaseModel):
    phone: str = Field(min_length=5, max_length=20)
    api_id: int | None = None
    api_hash: str | None = None


class CodeIn(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)


class PasswordIn(BaseModel):
    phone: str
    password: str


class SilentIn(BaseModel):
    init_data: str | None = None
    tg_user_id: int | None = None


def verify_telegram_init_data(init_data: str) -> dict | None:
    """Telegram Mini App initData'ni HMAC orqali tekshiradi va user'ni qaytaradi."""
    if not init_data or not settings.tg_bot_token:
        return None
    try:
        params = {k: v[0] for k, v in parse_qs(init_data).items()}
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={params[k]}" for k in sorted(params))
        secret_key = hmac.new(b"WebAppData", settings.tg_bot_token.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc_hash, received_hash):
            return None
        return _json.loads(params.get("user", "{}"))
    except Exception:
        return None


def _serialize_app_user(u: AppUser) -> dict:
    return {
        "is_owner": u.is_owner,
        "is_admin": u.is_admin,
        "is_vip": u.is_vip,
        "theme": u.theme,
    }


@router.post("/silent")
async def silent_auth(body: SilentIn):
    """Telegram Mini App ichida avtomatik kirish — telefon/kod/2FA talab qilmaydi.

    Telegram initData (HMAC) tekshiriladi, keyin o'sha Telegram foydalanuvchisiga
    bog'langan tayyor akkaunt topilib, yangi token qaytariladi.
    """
    user = None
    if body.init_data:
        user = verify_telegram_init_data(body.init_data)
    if user is None:
        # Xavfsizlik: faqat Telegram tomonidan imzolangan initData qabul qilinadi
        raise HTTPException(status_code=401, detail="Telegram tasdiqlovi topilmadi")
    tg_user_id = user.get("id")
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="Telegram foydalanuvchisi aniqlanmadi")

    async with SessionLocal() as db:
        app_user = (
            await db.execute(select(AppUser).where(AppUser.tg_user_id == int(tg_user_id)))
        ).scalar_one_or_none()
        if app_user is None:
            raise HTTPException(status_code=404, detail="Akkaunt topilmadi — avval ulang")
        acc = (
            await db.execute(select(Account).where(Account.id == app_user.account_id))
        ).scalar_one_or_none()
        if acc is None or acc.auth_step != "ready":
            raise HTTPException(status_code=401, detail="Akkaunt ulangan emas")

        token = create_token(acc.id)
        return {
            "token": token,
            "account": serialize_account(acc),
            "app_user": _serialize_app_user(app_user),
        }


@router.post("/start")
async def start(body: StartIn):
    try:
        return await start_login(body.phone, body.api_id, body.api_hash)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/verify")
async def verify(body: CodeIn):
    try:
        return await verify_code(body.phone, body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/password")
async def password(body: PasswordIn):
    try:
        return await submit_password(body.phone, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/accounts")
async def list_accounts():
    """Barcha akkauntlar (login ekrani + switch uchun)."""
    async with SessionLocal() as db:
        rows = (await db.execute(select(Account))).scalars().all()
        users = (await db.execute(select(AppUser))).scalars().all()
        info = {u.account_id: u for u in users}
        out = []
        for a in rows:
            item = serialize_account(a)
            u = info.get(a.id)
            item["app_user"] = {
                "is_owner": u.is_owner if u else False,
                "is_admin": u.is_admin if u else False,
                "is_vip": u.is_vip if u else False,
                "theme": u.theme if u else "default",
            }
            out.append(item)
        return {"accounts": out}


@router.post("/logout")
async def logout(body: dict | None = None):
    """Akkauntdan chiqish — sessiyani o'chirib, keyingi kirishda qayta ulashni talab qiladi."""
    from ..tg.manager import manager as _mgr

    account_id = (body or {}).get("account_id")
    async with SessionLocal() as db:
        q = select(Account)
        if account_id:
            q = q.where(Account.id == account_id)
        rows = (await db.execute(q)).scalars().all()
        for a in rows:
            await _mgr.stop_account(a.id)
            a.session_enc = ""
            a.auth_step = "none"
        await db.commit()
    return {"ok": True}