"""Chatlar va xabarlar API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..db import AppUser, get_session
from ..tg import actions
from .deps import require_account, resolve_account_id

router = APIRouter(prefix="/api", tags=["chats"])


class SendIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    text: str
    reply_to: int | None = None


@router.get("/chats")
async def chats(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        return {"dialogs": await actions.sync_dialogs(acc)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/chats/{dialog_id}/messages")
async def messages(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        msgs, has_more = await actions.sync_messages(acc, dialog_id, limit=limit, before=before)
        return {"messages": msgs, "has_more": has_more}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/chats/{dialog_id}/read")
async def read(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, account_id, db)
        await actions.mark_read(acc, dialog_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/messages")
async def send(
    body: SendIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    try:
        acc = await resolve_account_id(token_account, body.account_id, db)
        return await actions.send_text(acc, body.dialog_id, body.text, body.reply_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e