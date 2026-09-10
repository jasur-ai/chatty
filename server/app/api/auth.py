"""Login API: start (kod yuborish), verify (kod), password (2FA)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import Account, AppUser, SessionLocal
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