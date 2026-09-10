"""Lotus AI API — chat, sozlamalar, eslatmalar."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from ..db import Reminder, get_session
from ..lotus import LANGUAGES, lotus
from .deps import require_account

router = APIRouter(prefix="/api/lotus", tags=["lotus"])


class ChatIn(BaseModel):
    text: str


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
