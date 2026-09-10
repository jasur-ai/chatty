"""API umumiy bog'liqliklar: JWT auth, admin tekshiruv, xatoliklar."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import AppUser, get_session
from ..security import decode_token


async def require_account(
    authorization: str | None = Header(default=None),
) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token kerak")
    account_id = decode_token(authorization.removeprefix("Bearer ").strip())
    if account_id is None:
        raise HTTPException(status_code=401, detail="Token yaroqsiz")
    return account_id


async def resolve_account_id(
    token_account: int,
    requested: int | None,
    db: AsyncSession,
) -> int:
    """Admin/owner boshqa akkauntlarni ham ko'ra oladi."""
    if requested is None or requested == token_account:
        return token_account
    me = (
        await db.execute(select(AppUser).where(AppUser.account_id == token_account))
    ).scalar_one_or_none()
    if me and (me.is_owner or me.is_admin):
        return requested
    raise HTTPException(status_code=403, detail="Ruxsat yo'q")


async def require_admin(token_account: int, db: AsyncSession) -> AppUser:
    me = (
        await db.execute(select(AppUser).where(AppUser.account_id == token_account))
    ).scalar_one_or_none()
    if me is None or not (me.is_owner or me.is_admin):
        raise HTTPException(status_code=403, detail="Faqat admin")
    return me


async def require_vip(token_account: int, db: AsyncSession) -> AppUser:
    """VIP funksiya — faqat VIP foydalanuvchilar (yoki owner/admin)."""
    me = (
        await db.execute(select(AppUser).where(AppUser.account_id == token_account))
    ).scalar_one_or_none()
    if me is None or not (me.is_vip or me.is_owner or me.is_admin):
        raise HTTPException(status_code=403, detail="Bu VIP funksiya")
    return me