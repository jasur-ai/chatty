"""Bot-persona sozlamalari, profil rasmi, story, avto-javob va musiqa taklifi API.

- Bot nomi/rasmi: default akkaunt bilan bir xil, keyin alohida o'zgartiriladi.
- Profil rasmini o'zgartirish va story joylash (Telegram MTProto orqali).
- Avto-javob: matn + "belgilangan odamlar" ro'yxati + taklifiy matnlar.
- Musiqa taklifi: admin joylasa hammaga banner + like/dislike/reaksiya/komment.
"""
import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, delete

from ..db import (
    Account,
    AppUser,
    AutoReplyTarget,
    MusicPost,
    MusicReaction,
    get_session,
)
from ..storage import storage
from ..tg.filter import SUGGESTED_REPLIES
from ..tg.manager import manager
from ..tg.sync import serialize_account
from .deps import require_account, require_admin, resolve_account_id

router = APIRouter(prefix="/api/bot", tags=["bot"])


# ---------------- bot-persona ----------------
class BotSettingsIn(BaseModel):
    account_id: int | None = None
    bot_name: str | None = None
    update_tg_profile: bool = False  # Telegram profili ham o'zgartirilsinmi


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
        if body.update_tg_profile:
            client = manager.get(acc_id)
            if client:
                try:
                    from telethon import functions

                    await client(functions.account.UpdateProfileRequest(first_name=body.bot_name))
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
