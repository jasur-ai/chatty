"""Admin API — owner/admin uchun: akkauntlar kuzatuvi, VIP boshqaruvi."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..db import Account, AppUser, Dialog, Message, get_session
from ..tg.sync import serialize_account
from .deps import require_account, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class VipIn(BaseModel):
    account_id: int
    vip: bool


@router.get("/overview")
async def overview(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Barcha ulangan akkauntlar, chatlar va xabarlar soni (admin nazorati)."""
    await require_admin(token_account, db)
    async with db:
        accounts = (await db.execute(select(Account))).scalars().all()
        out = []
        for a in accounts:
            dialogs = (await db.execute(select(Dialog).where(Dialog.account_id == a.id))).scalars().all()
            msgs = (
                await db.execute(select(Message).where(Message.account_id == a.id))
            ).scalars().all()
            app_user = (
                await db.execute(select(AppUser).where(AppUser.account_id == a.id))
            ).scalar_one_or_none()
            out.append(
                {
                    **serialize_account(a),
                    "app_user": {
                        "is_owner": app_user.is_owner if app_user else False,
                        "is_admin": app_user.is_admin if app_user else False,
                        "is_vip": app_user.is_vip if app_user else False,
                        "theme": app_user.theme if app_user else "default",
                    },
                    "dialogs_count": len(dialogs),
                    "messages_count": len(msgs),
                }
            )
        return {"accounts": out}


@router.post("/vip")
async def set_vip(
    body: VipIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """User'ni VIP qilish/olib tashlash (faqat owner/admin)."""
    await require_admin(token_account, db)
    async with db:
        app_user = (
            await db.execute(select(AppUser).where(AppUser.account_id == body.account_id))
        ).scalar_one_or_none()
        if app_user is None:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
        app_user.is_vip = body.vip
        await db.commit()
        return {"ok": True, "is_vip": app_user.is_vip}