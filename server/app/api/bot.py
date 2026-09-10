"""Bot-persona sozlamalari, profil rasmi, story, avto-javob va musiqa taklifi API.

- Bot nomi/rasmi: default akkaunt bilan bir xil, keyin alohida o'zgartiriladi.
- Profil rasmini o'zgartirish va story joylash (Telegram MTProto orqali).
- Avto-javob: matn + "belgilangan odamlar" ro'yxati + taklifiy matnlar.
- Musiqa taklifi: admin joylasa hammaga banner + like/dislike/reaksiya/komment.
"""
import io
import tempfile
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, delete

from ..db import (
    Account,
    AppUser,
    AutoDeleteRule,
    AutoReplyTarget,
    MusicPost,
    MusicReaction,
    ScheduledMessage,
    get_session,
)
from ..storage import storage
from ..tg import actions
from ..tg.filter import SUGGESTED_REPLIES
from ..tg.manager import manager
from ..tg.sync import serialize_account
from .deps import require_account, require_admin, resolve_account_id

router = APIRouter(prefix="/api/bot", tags=["bot"])


# ---------------- bot-persona ----------------
class BotSettingsIn(BaseModel):
    account_id: int | None = None
    bot_name: str | None = None


@router.get("/settings")
async def get_bot_settings(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    acc = (await db.execute(select(Account).where(Account.id == acc_id))).scalar_one()
    return {
        "account": serialize_account(acc),
        "auto_reply": await _auto_reply_state(db, acc_id),
        "suggested_replies": SUGGESTED_REPLIES,
    }


@router.post("/settings")
async def update_bot_settings(
    body: BotSettingsIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    acc = (await db.execute(select(Account).where(Account.id == acc_id))).scalar_one()
    if body.bot_name is not None:
        acc.bot_name = body.bot_name
        # Telegram'da identifikatsiya akkauntning HAQIQIY profili orqali bo'ladi.
        # Anonimlik uchun akkaunt nomini bot nomiga o'zgartirish KERAK —
        # shunda odamlarga xabarlar "bot nomidan" ko'rinadi.
        client = manager.get(acc_id)
        if client:
            try:
                from telethon import functions

                await client(functions.account.UpdateProfileRequest(
                    first_name=body.bot_name,
                    last_name="",
                ))
                acc.first_name = body.bot_name
            except Exception:
                raise HTTPException(status_code=400, detail="Telegram profili yangilanmadi") from None
    await db.commit()
    return {"account": serialize_account(acc)}


@router.post("/photo")
async def set_bot_photo(
    account_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Profil rasmini o'zgartiradi (R2'ga saqlaydi + Telegram profiliga qo'yadi)."""
    acc_id = await resolve_account_id(token_account, account_id, db)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Bo'sh fayl")
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    key = storage.put(data, file.content_type or "image/jpeg", ext)

    client = manager.get(acc_id)
    if client:
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            from telethon import functions

            await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(tmp.name)))
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    acc = (await db.execute(select(Account).where(Account.id == acc_id))).scalar_one()
    acc.bot_photo = key
    await db.commit()
    return {"account": serialize_account(acc), "photo_url": storage.url(key)}


@router.post("/story")
async def post_story(
    account_id: int | None = Form(default=None),
    caption: str = Form(default=""),
    file: UploadFile = File(...),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    """Story joylaydi (rasm/video)."""
    acc_id = await resolve_account_id(token_account, account_id, db)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Bo'sh fayl")
    ext = ".jpg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    key = storage.put(data, file.content_type or "image/jpeg", ext)

    client = manager.get(acc_id)
    if client:
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            try:
                # MTProto story yuborish (Telethon 1.44)
                from telethon import functions

                await client(functions.stories.SendStoryRequest(
                    peer="me", media=await client.upload_file(tmp.name), caption=caption or None
                ))
            except Exception:
                # Fallback: saved messages'ga yuboramiz
                await client.send_file("me", tmp.name, caption=caption or None)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    return {"ok": True, "media_key": key}


# ---------------- avto-javob ----------------
class AutoReplyIn(BaseModel):
    account_id: int | None = None
    enabled: bool | None = None
    text: str | None = None
    selected_text: str | None = None
    schedule_from: str | None = None  # "HH:MM"
    schedule_to: str | None = None


class TargetIn(BaseModel):
    account_id: int | None = None
    tg_user_id: int
    name: str | None = None


async def _auto_reply_state(db, account_id: int) -> dict:
    app_user = (
        await db.execute(select(AppUser).where(AppUser.account_id == account_id))
    ).scalar_one_or_none()
    targets = (
        await db.execute(select(AutoReplyTarget).where(AutoReplyTarget.account_id == account_id))
    ).scalars().all()
    return {
        "enabled": app_user.auto_reply_enabled if app_user else False,
        "text": app_user.auto_reply_text if app_user else None,
        "selected_text": app_user.auto_reply_selected_text if app_user else None,
        "schedule_from": app_user.auto_reply_from if app_user else None,
        "schedule_to": app_user.auto_reply_to if app_user else None,
        "targets": [{"tg_user_id": t.tg_user_id, "name": t.name} for t in targets],
    }


@router.post("/auto-reply")
async def set_auto_reply(
    body: AutoReplyIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    app_user = (
        await db.execute(select(AppUser).where(AppUser.account_id == acc_id))
    ).scalar_one_or_none()
    if app_user is None:
        app_user = AppUser(account_id=acc_id)
        db.add(app_user)
    if body.enabled is not None:
        app_user.auto_reply_enabled = body.enabled
    if body.text is not None:
        app_user.auto_reply_text = body.text
    if body.selected_text is not None:
        app_user.auto_reply_selected_text = body.selected_text
    if body.schedule_from is not None:
        app_user.auto_reply_from = body.schedule_from
    if body.schedule_to is not None:
        app_user.auto_reply_to = body.schedule_to
    await db.commit()
    return {"ok": True}


@router.post("/auto-reply/targets")
async def add_target(
    body: TargetIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    row = (
        await db.execute(
            select(AutoReplyTarget).where(
                AutoReplyTarget.account_id == acc_id,
                AutoReplyTarget.tg_user_id == body.tg_user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(AutoReplyTarget(account_id=acc_id, tg_user_id=body.tg_user_id, name=body.name))
        await db.commit()
    return {"ok": True}


@router.delete("/auto-reply/targets/{tg_user_id}")
async def remove_target(
    tg_user_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    await db.execute(
        delete(AutoReplyTarget).where(
            AutoReplyTarget.account_id == acc_id, AutoReplyTarget.tg_user_id == tg_user_id
        )
    )
    await db.commit()
    return {"ok": True}


# ---------------- musiqa taklifi ----------------
class MusicIn(BaseModel):
    account_id: int | None = None
    title: str
    performer: str | None = None
    media_key: str | None = None
    caption: str = ""


class ReactionIn(BaseModel):
    music_post_id: int
    reaction: str = "like"  # like|dislike|heart|fire|clap
    comment: str | None = None
    user_tg_id: int


@router.get("/music")
async def list_music(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    posts = (
        await db.execute(
            select(MusicPost).where(MusicPost.account_id == acc_id).order_by(MusicPost.created_at.desc())
        )
    ).scalars().all()
    out = []
    for p in posts:
        reactions = (
            await db.execute(select(MusicReaction).where(MusicReaction.music_post_id == p.id))
        ).scalars().all()
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "performer": p.performer,
                "caption": p.caption,
                "media_url": storage.url(p.media_key) if p.media_key else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "reactions": [
                    {"user_tg_id": r.user_tg_id, "reaction": r.reaction, "comment": r.comment}
                    for r in reactions
                ],
            }
        )
    return {"music": out}


@router.post("/music")
async def create_music(
    body: MusicIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    me = (
        await db.execute(select(AppUser).where(AppUser.account_id == token_account))
    ).scalar_one_or_none()
    post = MusicPost(
        account_id=acc_id,
        title=body.title,
        performer=body.performer,
        media_key=body.media_key,
        caption=body.caption,
        created_by=me.tg_user_id if me else None,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return {"id": post.id, "title": post.title}


@router.post("/music/reaction")
async def react_music(
    body: ReactionIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    row = (
        await db.execute(
            select(MusicReaction).where(
                MusicReaction.music_post_id == body.music_post_id,
                MusicReaction.user_tg_id == body.user_tg_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            MusicReaction(
                music_post_id=body.music_post_id,
                user_tg_id=body.user_tg_id,
                reaction=body.reaction,
                comment=body.comment,
            )
        )
    else:
        row.reaction = body.reaction
        if body.comment is not None:
            row.comment = body.comment
    await db.commit()
    return {"ok": True}


# ================= Pro funksiyalar (barcha foydalanuvchilar uchun) =================

class ScheduleIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    text: str = ""
    media_key: str | None = None
    media_type: str | None = None
    send_at: str  # ISO datetime


class ForwardIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    msg_tg_id: int
    target_dialog_ids: list[int]


class AutoDeleteIn(BaseModel):
    account_id: int | None = None
    ttl_seconds: int


@router.post("/schedule")
async def schedule_message(
    body: ScheduleIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    from datetime import datetime as _dt

    try:
        send_at = _dt.fromisoformat(body.send_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Vaqt formati noto'g'ri") from None
    if send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)
    row = ScheduledMessage(
        account_id=acc_id,
        dialog_id=body.dialog_id,
        text=body.text,
        media_key=body.media_key,
        media_type=body.media_type,
        send_at=send_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"ok": True, "id": row.id}


@router.get("/schedule")
async def list_scheduled(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    rows = (
        await db.execute(
            select(ScheduledMessage)
            .where(ScheduledMessage.account_id == acc_id, ScheduledMessage.sent.is_(False))
            .order_by(ScheduledMessage.send_at)
        )
    ).scalars().all()
    return {
        "scheduled": [
            {
                "id": r.id,
                "dialog_id": r.dialog_id,
                "text": r.text,
                "send_at": r.send_at.isoformat(),
                "sent": r.sent,
            }
            for r in rows
        ]
    }


@router.delete("/schedule/{sid}")
async def delete_scheduled(
    sid: int,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    row = (await db.execute(select(ScheduledMessage).where(ScheduledMessage.id == sid))).scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"ok": True}


@router.post("/forward")
async def forward(
    body: ForwardIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.forward_message(acc_id, body.dialog_id, body.msg_tg_id, body.target_dialog_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    try:
        return {"results": await actions.search_messages(acc_id, q)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/export/{dialog_id}")
async def export(
    dialog_id: int,
    fmt: str = Query(default="json", pattern="^(json|csv)$"),
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    try:
        return await actions.export_dialog(acc_id, dialog_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/analytics")
async def analytics(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    return await actions.analytics(acc_id)


@router.post("/backup")
async def backup(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    return await actions.backup_chats(acc_id)


@router.get("/auto-delete")
async def get_auto_delete(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, account_id, db)
    row = (
        await db.execute(select(AutoDeleteRule).where(AutoDeleteRule.account_id == acc_id))
    ).scalar_one_or_none()
    return {"ttl_seconds": row.ttl_seconds if row else 0}


@router.post("/auto-delete")
async def set_auto_delete(
    body: AutoDeleteIn,
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    acc_id = await resolve_account_id(token_account, body.account_id, db)
    row = (
        await db.execute(select(AutoDeleteRule).where(AutoDeleteRule.account_id == acc_id))
    ).scalar_one_or_none()
    if row is None:
        row = AutoDeleteRule(account_id=acc_id, ttl_seconds=body.ttl_seconds)
        db.add(row)
    else:
        row.ttl_seconds = body.ttl_seconds
    await db.commit()
    return {"ok": True, "ttl_seconds": body.ttl_seconds}
