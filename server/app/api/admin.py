"""Admin API — owner/admin uchun: akkauntlar kuzatuvi, VIP, adminlar boshqaruvi."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from ..db import Account, Admin, AdminReport, AppUser, Dialog, Message, get_session
from ..scheduler import REPORT_INTERVALS, report_interval_hours
from ..tg.sync import serialize_account
from .deps import require_account, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class VipIn(BaseModel):
    account_id: int
    vip: bool


class AdminIn(BaseModel):
    tg_user_id: int


class IntervalIn(BaseModel):
    hours: int


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


@router.get("/users")
async def list_users(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Barcha foydalanuvchilar ro'yxati (akkaunt + app_user + statistikalar)."""
    await require_admin(token_account, db)
    async with db:
        accounts = (await db.execute(select(Account))).scalars().all()
        app_users = {u.account_id: u for u in (await db.execute(select(AppUser))).scalars().all()}
        out = []
        for a in accounts:
            u = app_users.get(a.id)
            dialogs_n = (
                await db.execute(select(Dialog).where(Dialog.account_id == a.id))
            ).scalars().all()
            msgs_n = (
                await db.execute(select(Message).where(Message.account_id == a.id))
            ).scalars().all()
            out.append(
                {
                    "id": a.id,
                    "phone": a.phone,
                    "first_name": a.first_name,
                    "username": a.username,
                    "bot_name": a.bot_name or a.first_name,
                    "auth_step": a.auth_step,
                    "is_active": a.is_active,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "tg_user_id": u.tg_user_id if u else None,
                    "is_owner": bool(u and u.is_owner),
                    "is_admin": bool(u and u.is_admin),
                    "is_vip": bool(u and u.is_vip),
                    "theme": u.theme if u else "default",
                    "dialogs_count": len(dialogs_n),
                    "messages_count": len(msgs_n),
                }
            )
        return {"users": out}


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


@router.get("/admins")
async def list_admins(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    async with db:
        rows = (await db.execute(select(Admin))).scalars().all()
        return {
            "admins": [
                {"tg_user_id": a.tg_user_id, "role": a.role, "added_by": a.added_by}
                for a in rows
            ]
        }


@router.post("/admins")
async def add_admin(
    body: AdminIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Yangi admin qo'shish (faqat owner)."""
    me = await require_admin(token_account, db)
    if not me.is_owner:
        raise HTTPException(status_code=403, detail="Faqat owner admin qo'sha oladi")
    async with db:
        row = (
            await db.execute(select(Admin).where(Admin.tg_user_id == body.tg_user_id))
        ).scalar_one_or_none()
        if row is None:
            db.add(Admin(tg_user_id=body.tg_user_id, role="admin", added_by=me.tg_user_id))
            await db.commit()
        return {"ok": True}


@router.delete("/admins/{tg_user_id}")
async def remove_admin(
    tg_user_id: int,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    me = await require_admin(token_account, db)
    if not me.is_owner:
        raise HTTPException(status_code=403, detail="Faqat owner admin o'chira oladi")
    async with db:
        await db.execute(delete(Admin).where(Admin.tg_user_id == tg_user_id))
        await db.commit()
        return {"ok": True}


@router.get("/report-interval")
async def get_report_interval(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    return {"hours": report_interval_hours(), "allowed": sorted(REPORT_INTERVALS)}


@router.post("/report-interval")
async def set_report_interval(
    body: IntervalIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    if body.hours not in REPORT_INTERVALS:
        raise HTTPException(status_code=400, detail="Oraliq 1/2/4/6/8 soat bo'lishi kerak")
    from ..config import settings

    settings.report_interval_hours = body.hours
    return {"ok": True, "hours": body.hours}


@router.get("/reports")
async def list_reports(
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_admin(token_account, db)
    async with db:
        rows = (
            await db.execute(select(AdminReport).order_by(AdminReport.created_at.desc()).limit(50))
        ).scalars().all()
        return {
            "reports": [
                {"id": r.id, "body": r.body, "created_at": r.created_at.isoformat()}
                for r in rows
            ]
        }