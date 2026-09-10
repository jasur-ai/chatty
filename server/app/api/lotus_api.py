"""Lotus AI API — chat, sozlamalar, eslatmalar, xulosa, tarjima."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..db import Reminder, get_session
from ..lotus import LANGUAGES, lotus
from .deps import require_account

router = APIRouter(prefix="/api/lotus", tags=["lotus"])


class ChatIn(BaseModel):
    text: str


class TextIn(BaseModel):
    text: str
    target: str | None = None  # translate uchun: uz/ru/en


class SettingsIn(BaseModel):
    language: str | None = None
    voice_enabled: bool | None = None


@router.post("/chat")
async def chat(body: ChatIn, token_account: int = Depends(require_account)):
    reply = await lotus.reply(body.text, context={"account_id": token_account})
    return {"reply": reply, "language": lotus.language}


@router.get("/settings")
async def get_settings(token_account: int = Depends(require_account)):
    return {
        "name": "Lotus 0.0.1",
        "language": lotus.language,
        "voice_enabled": lotus.voice_enabled,
        "languages": sorted(LANGUAGES),
    }


@router.post("/settings")
async def set_settings(body: SettingsIn, token_account: int = Depends(require_account)):
    if body.language is not None and body.language in LANGUAGES:
        lotus.language = body.language
    if body.voice_enabled is not None:
        lotus.voice_enabled = body.voice_enabled
    return {"language": lotus.language, "voice_enabled": lotus.voice_enabled}


@router.get("/reminders")
async def reminders(token_account: int = Depends(require_account), db=Depends(get_session)):
    rows = (
        await db.execute(
            select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at)
        )
    ).scalars().all()
    return {
        "reminders": [
            {"id": r.id, "text": r.text, "due_at": r.due_at.isoformat(), "done": r.done}
            for r in rows
        ]
    }


@router.post("/summarize")
async def summarize(body: TextIn, token_account: int = Depends(require_account)):
    """Matnni xulosa qilish (VIP — real LLM)."""
    out = await lotus.summarize(body.text, token_account)
    if out is None:
        # Offline: birinchi 2 jumla
        import re

        sents = re.split(r"(?<=[.!?])\s+", body.text.strip())
        out = " ".join(sents[:2]) if sents else body.text[:200]
    return {"summary": out}


@router.post("/translate")
async def translate(body: TextIn, token_account: int = Depends(require_account)):
    """Tarjima (VIP — real LLM)."""
    target = body.target or "uz"
    out = await lotus.translate(body.text, target, token_account)
    if out is None:
        raise HTTPException(status_code=403, detail="Tarjima VIP funksiya (real AI talab qiladi)")
    return {"translated": out}
