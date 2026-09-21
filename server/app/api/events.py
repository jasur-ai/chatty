"""Tadbir/event skaneri API.

Telegram papkasidagi kanal/guruhlardan so'nggi 1 hafta (sozlanishi) davomida
kalit so'zlar bo'yicha tadbirlarni topib, chiroyli jadval ko'rinishida beradi:
nomi, maqsadi, vaqti, o'tkaziladigan joyi.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..db import EventFolderConfig, EventItem, SessionLocal, get_session
from ..tg import eventscan
from .deps import require_account, resolve_account_id

router = APIRouter(prefix="/api/events", tags=["events"])
log = logging.getLogger("chatty.events_api")


class ConfigIn(BaseModel):
    account_id: int | None = None
    folder_id: int
    folder_title: str = ""
    days: int = 7
    extra_keywords: str = ""


class ScanIn(BaseModel):
    account_id: int | None = None
    folder_id: int | None = None
    days: int | None = None
    extra_keywords: str | None = None


def _serialize_event(e: EventItem) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "purpose": e.purpose,
        "when": e.when_,
        "place": e.place,
        "source_title": e.source_title,
        "source_kind": e.source_kind,
        "msg_tg_id": e.msg_tg_id,
        "msg_date": e.msg_date.isoformat() if e.msg_date else None,
        "by_ai": e.by_ai,
    }


@router.get("/folders")
async def folders(
    account_id: int | None = None,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Akkauntning Telegram papkalari (kanal/guruh borlari)."""
    acc_id = await resolve_account_id(token_account, account_id, db)
    try:
        return {"folders": await eventscan.list_folders(acc_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("Papkalar ro'yxati")
        raise HTTPException(status_code=500, detail=f"Papkalarni yuklab bo'lmadi: {e}") from e


@router.get("/config")
async def get_config(
    account_id: int | None = None,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    row = (
        await db.execute(select(EventFolderConfig).where(EventFolderConfig.account_id == acc_id))
    ).scalar_one_or_none()
    if row is None:
        return {"config": None}
    return {
        "config": {
            "folder_id": row.folder_id,
            "folder_title": row.folder_title,
            "days": row.days,
            "extra_keywords": row.extra_keywords,
            "last_scan_at": row.last_scan_at.isoformat() if row.last_scan_at else None,
        }
    }


@router.post("/config")
async def save_config(
    body: ConfigIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    row = (
        await db.execute(select(EventFolderConfig).where(EventFolderConfig.account_id == acc_id))
    ).scalar_one_or_none()
    if row is None:
        row = EventFolderConfig(account_id=acc_id)
        db.add(row)
    row.folder_id = body.folder_id
    row.folder_title = body.folder_title or ""
    row.days = max(1, min(body.days or 7, 30))
    row.extra_keywords = body.extra_keywords or ""
    await db.commit()
    return {"ok": True}


@router.post("/scan")
async def scan(
    body: ScanIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Papkadagi kanal/guruhlarni tekshirib, tadbirlar jadvalini qaytaradi."""
    acc_id = await resolve_account_id(token_account, body.account_id, db)

    # Sozlama: body'dan kelsa yangisi, aks holda saqlangan config
    config = (
        await db.execute(select(EventFolderConfig).where(EventFolderConfig.account_id == acc_id))
    ).scalar_one_or_none()
    folder_id = body.folder_id if body.folder_id is not None else (config.folder_id if config else None)
    days = body.days if body.days is not None else (config.days if config else 7)
    extra = body.extra_keywords if body.extra_keywords is not None else (config.extra_keywords if config else "")
    if not folder_id:
        raise HTTPException(status_code=400, detail="Avval papkani tanlang")

    try:
        result = await eventscan.scan_folder(acc_id, folder_id, days=days, extra_keywords=extra)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("Skanerlash xatosi")
        raise HTTPException(status_code=500, detail=f"Skanerlab bo'lmadi: {e}") from e

    # Natijani DB'ga saqlaymiz; config ham shu yerda bir marta yangilanadi
    # (bot va ilova bir xil so'nggi natijani ko'radi).
    await eventscan.persist_events(
        acc_id,
        result["events"],
        result["folder_title"],
        result["days"],
        folder_id=folder_id,
        extra_keywords=extra or "",
    )

    return {
        "events": result["events"],
        "scanned": result["scanned"],
        "folder_title": result["folder_title"],
        "days": result["days"],
    }


@router.get("")
async def list_events(
    account_id: int | None = None,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Saqlangan (oxirgi skanerlangan) tadbirlar jadvali."""
    acc_id = await resolve_account_id(token_account, account_id, db)
    rows = (
        await db.execute(
            select(EventItem).where(EventItem.account_id == acc_id).order_by(EventItem.msg_date.desc().nullslast())
        )
    ).scalars().all()
    config = (
        await db.execute(select(EventFolderConfig).where(EventFolderConfig.account_id == acc_id))
    ).scalar_one_or_none()
    return {
        "events": [_serialize_event(r) for r in rows],
        "config": {
            "folder_title": config.folder_title if config else None,
            "days": config.days if config else 7,
            "last_scan_at": config.last_scan_at.isoformat() if (config and config.last_scan_at) else None,
        },
    }
