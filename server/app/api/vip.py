"""VIP funksiyalar API — 20 ta mustaqil premium funksiya.

Har bir endpoint `require_vip` bilan himoyalangan (owner/admin ham VIP huquqiga ega).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select

from ..db import (
    AutoForwardRule,
    QuickReply,
    StarredMessage,
    VipTheme,
    get_session,
)
from ..tg import actions
from .deps import require_account, require_vip, resolve_account_id

router = APIRouter(prefix="/api/vip", tags=["vip"])


class DialogActionIn(BaseModel):
    account_id: int | None = None
    dialog_id: int


class EditIn(DialogActionIn):
    msg_tg_id: int
    text: str


class DeleteIn(DialogActionIn):
    msg_tg_id: int
    revoke: bool = True


class PinIn(DialogActionIn):
    pinned: bool = True


class FlagsIn(DialogActionIn):
    muted: bool | None = None
    archived: bool | None = None


class ReactIn(DialogActionIn):
    msg_tg_id: int
    reaction: str


class StarIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    tg_id: int
    text: str = ""
    dialog_title: str = ""


class QuickReplyIn(BaseModel):
    account_id: int | None = None
    label: str
    text: str


class ForwardRuleIn(BaseModel):
    account_id: int | None = None
    keyword: str
    source_dialog_id: int = 0
    target_dialog_id: int


class PollIn(DialogActionIn):
    question: str
    options: list[str]


class StickerIn(DialogActionIn):
    sticker_id: int | None = None
    emoji: str | None = None


class ThemeIn(BaseModel):
    account_id: int | None = None
    accent: str
    name: str = "custom"


class ProfileIn(BaseModel):
    account_id: int | None = None
    first_name: str | None = None
    bio: str | None = None
    username: str | None = None


class GroupManageIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    user_id: int
    action: str  # kick|ban|unban|promote|demote|set_title|rename
    title: str | None = None


class ChannelPostIn(BaseModel):
    account_id: int | None = None
    dialog_id: int
    text: str
    send_at: str
    silent: bool = False


# 1. Xabarni tahrirlash
@router.post("/edit")
async def edit(body: EditIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.edit_message(acc, body.dialog_id, body.msg_tg_id, body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 2. Xabarni o'chirish
@router.post("/delete")
async def delete(body: DeleteIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.delete_message(acc, body.dialog_id, body.msg_tg_id, body.revoke)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 3. Chat pin
@router.post("/pin")
async def pin(body: PinIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    return await actions.pin_dialog(acc, body.dialog_id, body.pinned)


# 4. Chat mute
# 5. Chat arxiv
@router.post("/flags")
async def flags(body: FlagsIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    return await actions.set_dialog_flags(acc, body.dialog_id, muted=body.muted, archived=body.archived)


# 6. Xabarga reaksiya
@router.post("/react")
async def react(body: ReactIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.react_message(acc, body.dialog_id, body.msg_tg_id, body.reaction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 7. Xabarni yulduzchalash
@router.post("/star")
async def star(body: StarIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    row = (
        await db.execute(
            select(StarredMessage).where(
                StarredMessage.account_id == acc,
                StarredMessage.dialog_id == body.dialog_id,
                StarredMessage.tg_id == body.tg_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            StarredMessage(
                account_id=acc,
                dialog_id=body.dialog_id,
                tg_id=body.tg_id,
                text=body.text,
                dialog_title=body.dialog_title,
            )
        )
        await db.commit()
    return {"ok": True, "starred": row is None}


@router.get("/starred")
async def starred_list(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    rows = (
        await db.execute(select(StarredMessage).where(StarredMessage.account_id == acc).order_by(StarredMessage.created_at.desc()))
    ).scalars().all()
    return {
        "starred": [
            {"id": r.id, "dialog_id": r.dialog_id, "tg_id": r.tg_id, "text": r.text, "dialog_title": r.dialog_title, "created_at": r.created_at.isoformat()}
            for r in rows
        ]
    }


@router.delete("/starred/{sid}")
async def star_remove(sid: int, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    await db.execute(delete(StarredMessage).where(StarredMessage.id == sid))
    await db.commit()
    return {"ok": True}


# 8. Tezkor javoblar
@router.get("/quick-replies")
async def quick_replies_list(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    rows = (
        await db.execute(select(QuickReply).where(QuickReply.account_id == acc).order_by(QuickReply.created_at))
    ).scalars().all()
    return {"quick_replies": [{"id": r.id, "label": r.label, "text": r.text} for r in rows]}


@router.post("/quick-replies")
async def quick_reply_add(body: QuickReplyIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    row = QuickReply(account_id=acc, label=body.label, text=body.text)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"ok": True, "id": row.id}


@router.delete("/quick-replies/{qid}")
async def quick_reply_remove(qid: int, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    await db.execute(delete(QuickReply).where(QuickReply.id == qid))
    await db.commit()
    return {"ok": True}


# 9. Maxsus mavzu
@router.get("/theme")
async def theme_get(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    row = (await db.execute(select(VipTheme).where(VipTheme.account_id == acc))).scalar_one_or_none()
    return {"accent": row.accent if row else "#3390ec", "name": row.name if row else "custom"}


@router.post("/theme")
async def theme_set(body: ThemeIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    row = (await db.execute(select(VipTheme).where(VipTheme.account_id == acc))).scalar_one_or_none()
    if row is None:
        row = VipTheme(account_id=acc, accent=body.accent, name=body.name)
        db.add(row)
    else:
        row.accent = body.accent
        row.name = body.name
    await db.commit()
    return {"ok": True, "accent": body.accent}


# 10. Media galereya
@router.get("/media-gallery/{dialog_id}")
async def media_gallery(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    try:
        return {"media": await actions.media_gallery(acc, dialog_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 11. O'qish hisoboti
@router.get("/read-receipts/{dialog_id}")
async def read_receipts(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    return await actions.read_receipts(acc, dialog_id)


# 12. Profil tahriri
@router.post("/profile")
async def profile(body: ProfileIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    return await actions.update_profile(acc, first_name=body.first_name, bio=body.bio, username=body.username)


# 13. So'rov yaratish
@router.post("/poll")
async def poll(body: PollIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.create_poll(acc, body.dialog_id, body.question, body.options)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 14. Stiker/GIF yuborish
@router.post("/sticker")
async def sticker(body: StickerIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.send_sticker(acc, body.dialog_id, body.sticker_id, body.emoji)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 15. Kontaktlar ro'yxati
@router.get("/contacts")
async def contacts(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    return {"contacts": await actions.contacts_list(acc)}


# 16. Avto-forward qoidalari
@router.get("/auto-forward")
async def auto_forward_list(
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    rows = (
        await db.execute(select(AutoForwardRule).where(AutoForwardRule.account_id == acc).order_by(AutoForwardRule.created_at))
    ).scalars().all()
    return {
        "rules": [
            {"id": r.id, "keyword": r.keyword, "source_dialog_id": r.source_dialog_id, "target_dialog_id": r.target_dialog_id, "enabled": r.enabled}
            for r in rows
        ]
    }


@router.post("/auto-forward")
async def auto_forward_add(body: ForwardRuleIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    row = AutoForwardRule(
        account_id=acc,
        keyword=body.keyword,
        source_dialog_id=body.source_dialog_id,
        target_dialog_id=body.target_dialog_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"ok": True, "id": row.id}


@router.delete("/auto-forward/{rid}")
async def auto_forward_remove(rid: int, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    await db.execute(delete(AutoForwardRule).where(AutoForwardRule.id == rid))
    await db.commit()
    return {"ok": True}


# 17. Guruh boshqaruvi
@router.post("/group-manage")
async def group_manage(body: GroupManageIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    try:
        return await actions.group_manage(acc, body.dialog_id, body.user_id, body.action, body.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 18. Guruh a'zolari
@router.get("/members/{dialog_id}")
async def members(
    dialog_id: int,
    account_id: int | None = Query(default=None),
    token_account: int = Depends(require_account),
    db=Depends(get_session),
):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, account_id, db)
    try:
        return {"members": await actions.group_members(acc, dialog_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# 19. Kanalga rejalashtirilgan post
@router.post("/channel-post")
async def channel_post(body: ChannelPostIn, token_account: int = Depends(require_account), db=Depends(get_session)):
    await require_vip(token_account, db)
    acc = await resolve_account_id(token_account, body.account_id, db)
    from datetime import datetime as _dt

    try:
        send_at = _dt.fromisoformat(body.send_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Vaqt formati noto'g'ri") from None
    if send_at.tzinfo is None:
        from datetime import timezone as _tz

        send_at = send_at.replace(tzinfo=_tz.utc)
    try:
        return await actions.schedule_channel_post(acc, body.dialog_id, body.text, send_at, body.silent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
