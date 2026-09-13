"""Telegram Bot API orqali xabarnomalar + delegat (vakil) relay.

Ikki vazifa:

1) **Xabarnoma**: app ochiq bo'lmaganda, bot odamlarga xabarlar kelganda egasiga push yuboradi.

2) **Delegat-bot (vakil)**: begona odam @chattiey_bot'ga yozadi → bot egasiga forward qiladi →
   egasi (mini app yoki Telegram'da reply orqali) javob beradi → javob bot nomidan begonaga yetadi.
"""
import asyncio
import json
import logging

import httpx

from .config import settings

log = logging.getLogger("chatty.notify")

API = "https://api.telegram.org"


def fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def media_brief(msg) -> str | None:
    """Telethon Message'dan qisqa xabarnoma matni. (emoji yo'q — faqat matn)"""
    if msg.voice:
        return f"{fmt_duration(msg.voice.duration)} min audio"
    if msg.audio:
        return f"{fmt_duration(msg.audio.duration)} min musiqa"
    if msg.video:
        return f"{fmt_duration(msg.video.duration)} min video"
    if msg.video_note:
        return "Dumaloq video"
    if msg.photo:
        return "Rasm"
    if msg.sticker:
        return "Stiker"
    if msg.animation:
        return "GIF"
    if msg.poll:
        return "So'rov"
    if msg.document:
        name = ""
        for attr in msg.document.attributes:
            if hasattr(attr, "file_name") and attr.file_name:
                name = attr.file_name
        return f"Fayl: {name}" if name else "Fayl"
    return None


def media_info_of_bot_msg(msg: dict) -> tuple[str, str | None]:
    """Bot API message → (media_type, file_id)."""
    if msg.get("photo"):
        return "photo", msg["photo"][-1]["file_id"]
    if msg.get("voice"):
        return "voice", msg["voice"]["file_id"]
    if msg.get("video_note"):
        return "round", msg["video_note"]["file_id"]
    if msg.get("video"):
        return "video", msg["video"]["file_id"]
    if msg.get("audio"):
        return "audio", msg["audio"]["file_id"]
    if msg.get("document"):
        return "file", msg["document"]["file_id"]
    if msg.get("sticker"):
        return "sticker", msg["sticker"]["file_id"]
    if msg.get("animation"):
        return "gif", msg["animation"]["file_id"]
    return "none", None


class BotNotifier:
    def __init__(self) -> None:
        self.token = settings.tg_bot_token
        self.enabled = bool(self.token)
        self.owner_id = settings.owner_id
        self.bot_id: int | None = None
        self._offset = 0
        self._task: asyncio.Task | None = None

    @property
    def base(self) -> str:
        return f"{API}/bot{self.token}"

    # ---------------- pastki darajadagi Bot API chaqiruvlari ----------------
    async def get_me(self) -> dict | None:
        if not self.enabled:
            return None
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base}/getMe", timeout=10)
            return r.json().get("result")

    async def _post(self, method: str, payload: dict) -> dict | None:
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient() as c:
                r = await c.post(f"{self.base}/{method}", json=payload, timeout=20)
            return r.json()
        except Exception as e:  # noqa: BLE001
            log.warning("Bot API %s xato: %s", method, e)
            return None

    async def send_notification(
        self, chat_id: int, text: str, *, button_url: str | None = None, button_text: str = "Javob yozish"
    ) -> bool:
        if not self.enabled:
            return False
        payload: dict = {"chat_id": chat_id, "text": text}
        if button_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": button_text, "url": button_url}]]
            }
        data = await self._post("sendMessage", payload)
        return bool(data and data.get("ok"))

    async def send_text(self, chat_id: int, text: str) -> int | None:
        """Matn yuboradi va yangi message_id qaytaradi."""
        data = await self._post("sendMessage", {"chat_id": chat_id, "text": text})
        if data and data.get("ok"):
            return data["result"]["message_id"]
        return None

    async def forward_message(self, from_chat_id: int, message_id: int, to_chat_id: int) -> int | None:
        """Xabarni forward qiladi (media/voice bilan) va yangi message_id qaytaradi."""
        data = await self._post(
            "forwardMessage",
            {"chat_id": to_chat_id, "from_chat_id": from_chat_id, "message_id": message_id},
        )
        if data and data.get("ok"):
            return data["result"]["message_id"]
        return None

    async def send_media(self, chat_id: int, file_id: str, media_type: str, text: str = "") -> int | None:
        """Begonaga media yuboradi (photo/voice/video/file)."""
        method, field = {
            "photo": ("sendPhoto", "photo"),
            "voice": ("sendVoice", "voice"),
            "audio": ("sendAudio", "audio"),
            "video": ("sendVideo", "video"),
            "round": ("sendVideoNote", "video_note"),
            "gif": ("sendAnimation", "animation"),
            "file": ("sendDocument", "document"),
        }.get(media_type, ("sendMessage", None))
        if field is None:
            return await self.send_text(chat_id, text)
        payload = {"chat_id": chat_id, field: file_id}
        if text:
            payload["caption"] = text
        data = await self._post(method, payload)
        if data and data.get("ok"):
            return data["result"]["message_id"]
        return None

    async def get_file(self, file_id: str) -> bytes | None:
        """getFile orqali faylni yuklab oladi (mini app media ko'rsatish uchun)."""
        data = await self._post("getFile", {"file_id": file_id})
        if not data or not data.get("ok"):
            return None
        path = data["result"].get("file_path")
        if not path:
            return None
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{API}/file/bot{self.token}/{path}", timeout=60)
                return r.content
        except Exception as e:  # noqa: BLE001
            log.warning("getFile yuklash xato: %s", e)
            return None

    # ---------------- polling (callback tugmalar + /start + delegat) ----------------
    async def start_polling(self) -> None:
        if not self.enabled or self._task is not None:
            return
        me = await self.get_me()
        if me:
            self.bot_id = me.get("id")
        self._task = asyncio.create_task(self._poll_loop())
        asyncio.create_task(self._setup_commands())
        log.info("Bot polling boshlandi (@chattiey_bot)")

    async def _setup_commands(self) -> None:
        commands = [
            {"command": "start", "description": "Botni ishga tushirish"},
            {"command": "open", "description": "Chatty ilovasini ochish"},
            {"command": "help", "description": "Yordam va qo'llanma"},
            {"command": "status", "description": "Ulanish holatini ko'rish"},
        ]
        try:
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"{self.base}/setMyCommands", json={"commands": commands}, timeout=10
                )
        except Exception as e:  # noqa: BLE001
            log.warning("Bot komandalari o'rnatilmadi: %s", e)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("Bot polling xato: %s", e)
            await asyncio.sleep(2)

    async def _poll_once(self) -> None:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{self.base}/getUpdates",
                params={
                    "offset": self._offset,
                    "timeout": 25,
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                },
                timeout=35,
            )
            data = r.json()
            if not data.get("ok"):
                return
            for upd in data.get("result", []):
                self._offset = upd["update_id"] + 1
                await self._handle_update(upd)

    async def _handle_update(self, upd: dict) -> None:
        if "callback_query" in upd:
            await self._answer_callback(upd["callback_query"])
            return
        if "message" not in upd:
            return
        msg = upd["message"]
        chat = msg.get("chat", {})
        if chat.get("type") != "private":
            return
        from_id = msg.get("from", {}).get("id")
        if self.bot_id and from_id == self.bot_id:
            return  # o'z aks-sadosi
        text = (msg.get("text") or "").strip()
        cmd = text.split()[0].split("@")[0] if text.startswith("/") else ""

        if from_id == self.owner_id:
            # Owner: komandalar + delegat javob (reply orqali)
            if cmd in ("/start", "/open", "/help", "/status"):
                await self._handle_command(chat["id"], cmd)
            elif msg.get("reply_to_message"):
                await self._handle_owner_reply(msg)
            else:
                await self.send_notification(
                    chat["id"],
                    "Begonaga javob berish uchun forward qilingan xabarga javob (reply) yozing "
                    "yoki Chatty ilovasini oching.",
                )
        else:
            # Begona odam: har bir xabar (shu jumladan /start) egaga relay qilinadi.
            await self._handle_stranger_message(msg)

    async def _handle_command(self, chat_id: int, cmd: str) -> None:
        if cmd == "/start":
            await self._send_open_button(
                chat_id,
                "Chatty xabarnoma botiga xush kelibsiz.\n"
                "Sizga kelgan xabarlar haqida shu yerda xabar beramiz.\n\n"
                "Ilovani ochib, akkauntlaringizni boshqaring.",
            )
        elif cmd == "/open":
            await self._send_open_button(chat_id, "Chatty ilovasini ochish uchun tugmani bosing.")
        elif cmd == "/help":
            await self.send_notification(
                chat_id,
                "Chatty — Telegram akkauntlarini boshqarish platformasi.\n\n"
                "Qanday ishlaydi:\n"
                "1. Chatty ilovasida akkauntni ulaysiz (telefon + kod + 2FA)\n"
                "2. Sizga xabar kelganda shu bot xabar beradi\n"
                "3. \"Javob yozish\" tugmasi bilan ilovani ochasiz\n\n"
                "Komandalar:\n"
                "/start — boshlash\n"
                "/open — ilovani ochish\n"
                "/help — yordam\n"
                "/status — ulanish holati",
            )
        elif cmd == "/status":
            from .tg.manager import manager  # noqa: PLC0415

            n = len(manager.clients)
            await self.send_notification(
                chat_id,
                f"Ulangan akkauntlar: {n} ta.\n"
                "Ulanish holatini to'liq ko'rish uchun ilovani oching.",
            )

    async def _send_open_button(self, chat_id: int, text: str) -> None:
        await self.send_notification(
            chat_id,
            text,
            button_url=settings.bot_reply_url or None,
            button_text="Chatty ochish",
        )

    async def _answer_callback(self, cq: dict) -> None:
        qid = cq["id"]
        text = "Chatty ilovasida javob yozing"
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{self.base}/answerCallbackQuery",
                json={"callback_query_id": qid, "text": text, "show_alert": False},
                timeout=10,
            )

    # ---------------- delegat relay ----------------
    async def _handle_stranger_message(self, msg: dict) -> None:
        """Begona odam botga yozdi — DB'ga saqlab, egaga relay qilamiz."""
        from sqlalchemy import select

        from .db import DelegateDialog, DelegateMessage, SessionLocal, utcnow
        from .ws import ws_manager

        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
        name = from_user.get("first_name") or ""
        username = from_user.get("username")
        text = (msg.get("text") or msg.get("caption") or "").strip()
        media_type, file_id = media_info_of_bot_msg(msg)

        notif_id = await self.forward_message(chat_id, msg["message_id"], self.owner_id)

        async with SessionLocal() as db:
            dlg = (
                await db.execute(
                    select(DelegateDialog).where(DelegateDialog.bot_chat_id == chat_id)
                )
            ).scalar_one_or_none()
            if dlg is None:
                dlg = DelegateDialog(bot_chat_id=chat_id, first_name=name, username=username)
                db.add(dlg)
                await db.flush()
            else:
                if name:
                    dlg.first_name = name
                if username:
                    dlg.username = username
            dlg.last_msg_text = text or (media_type if media_type != "none" else "")
            dlg.last_msg_date = utcnow()
            dlg.last_out = False
            dlg.unread_count += 1
            row = DelegateMessage(
                dialog_id=dlg.id,
                direction="in",
                text=text,
                media_type=media_type,
                file_id=file_id,
                owner_notify_id=notif_id,
            )
            db.add(row)
            await db.flush()
            row_id = row.id
            serialized_dlg = _serialize_delegate_dialog(dlg)
            serialized_msg = _serialize_delegate_message(row)
            await db.commit()

        # Media bo'lsa — fonda yuklab keshga olamiz (Bot API getFile orqali,
        # MTProto client'ni bloklamaydi). Keyin media_url ochiq /api/media/{key} bo'ladi.
        if media_type != "none" and file_id:
            asyncio.create_task(self._cache_delegate_media(row_id, file_id, media_type))

        # Real-time: egaga (owner) WS orqali yangi suhbat/xabar
        owner_acc = await _owner_account_id()
        if owner_acc is not None:
            await ws_manager.broadcast(
                owner_acc,
                {"type": "delegate_message", "dialog": serialized_dlg, "message": serialized_msg},
            )

    async def _handle_owner_reply(self, msg: dict) -> None:
        """Egasi Telegram'da forward qilingan xabarga reply yozdi — begonaga yetkazamiz."""
        from sqlalchemy import select

        from .db import DelegateDialog, DelegateMessage, SessionLocal, utcnow
        from .ws import ws_manager

        reply = msg.get("reply_to_message") or {}
        reply_id = reply.get("message_id")
        if not reply_id:
            return
        text = (msg.get("text") or msg.get("caption") or "").strip()
        media_type, file_id = media_info_of_bot_msg(msg)

        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(DelegateMessage).where(DelegateMessage.owner_notify_id == reply_id)
                )
            ).scalar_one_or_none()
            if row is None:
                await self.send_notification(
                    msg["chat"]["id"],
                    "Bu xabarga bog'liq suhbat topilmadi. Ilovani ochib javob yozing.",
                )
                return
            dlg = (
                await db.execute(
                    select(DelegateDialog).where(DelegateDialog.id == row.dialog_id)
                )
            ).scalar_one_or_none()
            if dlg is None:
                return

            # Begonaga yetkazish
            if media_type != "none" and file_id:
                await self.send_media(dlg.bot_chat_id, file_id, media_type, text)
            elif text:
                await self.send_text(dlg.bot_chat_id, text)
            else:
                return

            out = DelegateMessage(dialog_id=dlg.id, direction="out", text=text, media_type=media_type, file_id=file_id)
            db.add(out)
            dlg.last_msg_text = text or (media_type if media_type != "none" else "")
            dlg.last_msg_date = utcnow()
            dlg.last_out = True
            await db.flush()
            dlg_id = dlg.id
            out_id = out.id
            serialized_dlg = _serialize_delegate_dialog(dlg)
            serialized_msg = _serialize_delegate_message(out)
            await db.commit()

        owner_acc = await _owner_account_id()
        if owner_acc is not None:
            await ws_manager.broadcast(
                owner_acc,
                {"type": "delegate_message", "dialog": serialized_dlg, "message": serialized_msg},
            )


    async def _cache_delegate_media(self, message_id: int, file_id: str, media_type: str) -> None:
        """Begona yuborgan media'ni fonda yuklab keshga olamiz."""
        from sqlalchemy import select

        from .db import DelegateMessage, SessionLocal
        from .storage import storage

        try:
            data = await self.get_file(file_id)
            if not data:
                return
            ext = _ext_for(media_type)
            mime = _mime_for(media_type)
            key = storage.put(data, mime, ext)
            async with SessionLocal() as db:
                m = (
                    await db.execute(select(DelegateMessage).where(DelegateMessage.id == message_id))
                ).scalar_one_or_none()
                if m is None:
                    return
                m.media_key = key
                await db.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("Delegat media keshlash xato: %s", e)


def _ext_for(media_type: str) -> str:
    return {
        "photo": ".jpg",
        "voice": ".ogg",
        "audio": ".mp3",
        "video": ".mp4",
        "round": ".mp4",
        "gif": ".mp4",
        "file": ".bin",
        "sticker": ".webp",
    }.get(media_type, ".bin")


def _mime_for(media_type: str) -> str:
    return {
        "photo": "image/jpeg",
        "voice": "audio/ogg",
        "audio": "audio/mpeg",
        "video": "video/mp4",
        "round": "video/mp4",
        "gif": "video/mp4",
        "file": "application/octet-stream",
        "sticker": "image/webp",
    }.get(media_type, "application/octet-stream")


def _serialize_delegate_dialog(d) -> dict:
    return {
        "id": d.id,
        "bot_chat_id": d.bot_chat_id,
        "first_name": d.first_name,
        "username": d.username,
        "last_msg_text": d.last_msg_text,
        "last_msg_date": d.last_msg_date.isoformat() if d.last_msg_date else None,
        "last_out": d.last_out,
        "unread_count": d.unread_count,
        "pinned": d.pinned,
    }


def _serialize_delegate_message(m) -> dict:
    from .storage import storage

    media_url = None
    if m.media_key and storage.exists(m.media_key):
        media_url = storage.url(m.media_key)
    elif m.media_type != "none" and getattr(m, "file_id", None):
        media_url = f"/api/delegate/media/{m.id}"
    return {
        "id": m.id,
        "dialog_id": m.dialog_id,
        "direction": m.direction,
        "text": m.text,
        "media_type": m.media_type,
        "media_url": media_url,
        "date": m.date.isoformat() if m.date else None,
    }


async def _owner_account_id() -> int | None:
    """Owner (bot egasi) akkauntining id'sini qaytaradi (WS broadcast uchun)."""
    from sqlalchemy import select

    from .db import AppUser, SessionLocal

    async with SessionLocal() as db:
        u = (
            await db.execute(select(AppUser).where(AppUser.is_owner.is_(True)))
        ).scalar_one_or_none()
        return u.account_id if u else None


notifier = BotNotifier()
