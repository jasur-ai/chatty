"""Telegram Bot API orqali xabarnomalar + delegat (vakil) relay.

Ikki vazifa:

1) **Xabarnoma**: app ochiq bo'lmaganda, bot odamlarga xabarlar kelganda egasiga push yuboradi.

2) **Delegat-bot (vakil)**: begona odam @chattiey_bot'ga yozadi → bot egasiga forward qiladi →
   egasi (mini app yoki Telegram'da reply orqali) javob beradi → javob bot nomidan begonaga yetadi.
"""
import asyncio
import json
import logging
from datetime import timedelta
from pathlib import Path

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
        self,
        chat_id: int,
        text: str,
        *,
        button_url: str | None = None,
        button_text: str = "Javob yozish",
        force_reply: bool = False,
        placeholder: str = "Shu yerga javob yozing…",
        reply_to_message_id: int | None = None,
        parse_html: bool = False,
    ) -> int | None:
        """Xabarnoma yuboradi. `force_reply=True` bo'lsa javob oynasi shu xabar ostida ochiladi.

        message_id qaytaradi — bot ichida javob berish kontekstini bog'lash uchun.
        """
        if not self.enabled:
            return None
        payload: dict = {"chat_id": chat_id, "text": text}
        if parse_html:
            payload["parse_mode"] = "HTML"
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        if force_reply:
            # Saytga yo'naltirmasdan — to'g'ridan-to'g'ri Telegram ichida javob
            payload["reply_markup"] = {
                "force_reply": True,
                "selective": True,
                "input_field_placeholder": placeholder,
            }
        elif button_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": button_text, "url": button_url}]]
            }
        data = await self._post("sendMessage", payload)
        if data and data.get("ok"):
            return data["result"]["message_id"]
        return None

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

    async def send_media_file(
        self, chat_id: int, data: bytes, filename: str, media_type: str, caption: str = ""
    ) -> int | None:
        """Begonaga raw fayl yuboradi (multipart orqali — file_id shart emas)."""
        from . import convert as _convert

        # webm → Telegram formati (ogg/mp4) — aks holda "fayl" bo'lib ketadi.
        # Konvertatsiya bo'lmasa hech bo'lmaganda fayl sifatida yetkazib beramiz.
        ext = Path(filename).suffix or ".bin"
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        mime = _mime_for(media_type)
        if media_type == "voice":
            c = await asyncio.to_thread(_convert.to_voice_note, data, ext)
            if c:
                data, filename, mime = c, stem + ".ogg", "audio/ogg"
            else:
                media_type = "file"
        elif media_type == "round":
            c = await asyncio.to_thread(_convert.to_video_note, data, ext)
            if c:
                data, filename, mime = c, stem + ".mp4", "video/mp4"
            else:
                media_type = "file"
        elif media_type == "video" and ext.lower() != ".mp4":
            c = await asyncio.to_thread(_convert.to_video, data, ext)
            if c:
                data, filename, mime = c, stem + ".mp4", "video/mp4"
            else:
                media_type = "file"

        method, field = {
            "photo": ("sendPhoto", "photo"),
            "voice": ("sendVoice", "voice"),
            "audio": ("sendAudio", "audio"),
            "video": ("sendVideo", "video"),
            "round": ("sendVideoNote", "video_note"),
            "file": ("sendDocument", "document"),
        }.get(media_type, ("sendDocument", "document"))
        if media_type == "file":
            mime = _mime_for("file")
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                files = {field: (filename, data, mime)}
                payload: dict = {"chat_id": str(chat_id)}
                if caption:
                    payload["caption"] = caption
                r = await c.post(f"{self.base}/{method}", data=payload, files=files)
                j = r.json()
                if j.get("ok"):
                    return j["result"]["message_id"]
                log.warning("Bot API %s xato: %s", method, j.get("description"))
                return None
        except Exception as e:  # noqa: BLE001
            log.warning("Bot API %s xato: %s", method, e)
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
        """Bot menyusiga komandalarni qo'shadi (Telegram'da '/' bosilganda ko'rinadi)."""
        commands = [
            {"command": "start", "description": "Botni ishga tushirish"},
            {"command": "open", "description": "Chatty ilovasini ochish"},
            {"command": "list", "description": "Botga yozgan odamlar ro'yxati"},
            {"command": "r", "description": "Javob yozish: /r <raqam> matn"},
            {"command": "chats", "description": "Bo'limlar: chatlar, guruhlar, kanallar, botlar"},
            {"command": "events", "description": "Tadbirlar: papkadagi kanal/guruhlardan event topish"},
            {"command": "reply", "description": "Javob yozish (qisqa: /r)"},
            {"command": "music", "description": "Musiqalar ro'yxati"},
            {"command": "autoreply", "description": "Avto-javobni yoqish/o'chirish"},
            {"command": "users", "description": "Foydalanuvchilar ro'yxati (admin)"},
            {"command": "vip", "description": "Foydalanuvchini VIP qilish (admin)"},
            {"command": "report", "description": "AI hisobot (admin)"},
            {"command": "status", "description": "Ulanish holatini ko'rish"},
            {"command": "help", "description": "Yordam va qo'llanma"},
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
            # Owner: komandalar + bot ichida javob (xabarnomaga reply)
            if cmd:
                await self._handle_command(chat["id"], cmd, msg)
                return
            if msg.get("reply_to_message"):
                # Avval bot ichidagi javob konteksti (oddiy chat yoki delegat),
                # keyin eski delegat forward sxemasi.
                if await self._handle_reply_in_bot(msg):
                    return
                await self._handle_owner_reply(msg)
                return
            await self.send_notification(
                chat["id"],
                "Javob yozish uchun kelgan xabar ostidagi 'Javob yozish' tugmasini bosing "
                "yoki shu xabarga reply yozing. Ro'yxat: /list  ·  Javob: /r <raqam> matn",
                force_reply=True,
                placeholder="Masalan: /r 1 salom",
            )
        else:
            # Begona odam: har bir xabar (shu jumladan /start) egaga relay qilinadi.
            await self._handle_stranger_message(msg)

    async def _handle_command(self, chat_id: int, cmd: str, msg: dict | None = None) -> None:
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
                "3. Javobni shu bot ichida yozasiz — xabar akkauntingiz nomidan boradi\n\n"
                "Komandalar:\n"
                "/start — boshlash\n"
                "/open — ilovani ochish\n"
                "/list — botga yozgan odamlar\n"
                "/r <raqam> matn — javob yozish\n"
                "/chats — bo'limlar statistikasi\n"
                "/events — tadbirlar (papkadagi kanal/guruhlar)\n"
                "/music — musiqalar\n"
                "/autoreply — avto-javobni yoqish/o'chirish\n"
                "/users — foydalanuvchilar (admin)\n"
                "/vip <id> — VIP qilish (admin)\n"
                "/report — AI hisobot (admin)\n"
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
        elif cmd == "/list":
            await self._cmd_list_dialogs(chat_id)
        elif cmd == "/music":
            await self._cmd_music(chat_id)
        elif cmd == "/autoreply":
            await self._cmd_autoreply(chat_id, msg)
        elif cmd == "/users":
            await self._cmd_users(chat_id)
        elif cmd == "/vip":
            await self._cmd_vip(chat_id, msg)
        elif cmd == "/report":
            await self._cmd_report(chat_id)
        elif cmd in ("/r", "/reply", "/javob"):
            await self._cmd_reply(chat_id, msg)
        elif cmd == "/chats":
            await self._cmd_chats(chat_id)
        elif cmd in ("/events", "/tadbirlar"):
            await self._cmd_events(chat_id, msg)

    async def _cmd_list_dialogs(self, chat_id: int) -> None:
        from sqlalchemy import select

        from .db import DelegateDialog, SessionLocal

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(DelegateDialog).order_by(DelegateDialog.last_msg_date.desc().nullslast()).limit(15)
                )
            ).scalars().all()
        if not rows:
            await self.send_notification(chat_id, "Hozircha hech kim botga yozmagan.")
            return
        lines = ["Botga yozganlar:"]
        for i, d in enumerate(rows, 1):
            name = d.first_name or d.username or "Foydalanuvchi"
            last = (d.last_msg_text or "")[:40]
            lines.append(f"{i}. {name} — {last}")
        await self.send_notification(chat_id, "\n".join(lines))

    async def _cmd_chats(self, chat_id: int) -> None:
        """Chatlar bo'limlar bo'yicha statistika (chatlar/guruhlar/kanallar/botlar)."""
        from sqlalchemy import select  # noqa: PLC0415

        from .db import Account, Dialog, SessionLocal  # noqa: PLC0415

        async with SessionLocal() as db:
            acc = (
                await db.execute(select(Account).where(Account.auth_step == "ready").limit(1))
            ).scalar_one_or_none()
            if acc is None:
                await self.send_notification(chat_id, "Akkaunt topilmadi.")
                return
            rows = (
                await db.execute(select(Dialog).where(Dialog.account_id == acc.id))
            ).scalars().all()
        counts = {"user": 0, "group": 0, "channel": 0, "bot": 0}
        for d in rows:
            kind = d.kind or ("group" if d.peer_type == "chat" else "user")
            counts[kind] = counts.get(kind, 0) + 1
        total = sum(counts.values())
        await self.send_notification(
            chat_id,
            "Bo'limlar (jami {}):\n"
            "Chatlar: {}\n"
            "Guruhlar: {}\n"
            "Kanallar: {}\n"
            "Botlar: {}\n\n"
            "Ilovada ular alohida bo'limlar ko'rinishida.".format(
                total, counts["user"], counts["group"], counts["channel"], counts["bot"]
            ),
        )

    async def _cmd_events(self, chat_id: int, msg: dict | None) -> None:
        """Tadbirlar skaneri: papkadagi kanal/guruhlardan so'nggi 1 haftalik event topish.

        /events — saqlangan papkani tekshiradi (yoki papkalar ro'yxatini ko'rsatadi)
        /events <raqam> — ro'yxatdagi <raqam>-papkani tanlab tekshiradi
        """
        from sqlalchemy import select

        from .db import Account, EventFolderConfig, SessionLocal
        from .tg import eventscan

        async with SessionLocal() as db:
            acc = (
                await db.execute(
                    select(Account).where(Account.auth_step == "ready", Account.is_active.is_(True)).limit(1)
                )
            ).scalar_one_or_none()
            if acc is None:
                await self.send_notification(chat_id, "Akkaunt ulangan emas. Ilovada akkauntni ulang.")
                return
            config = (
                await db.execute(select(EventFolderConfig).where(EventFolderConfig.account_id == acc.id))
            ).scalar_one_or_none()
            acc_id = acc.id

        arg = (msg.get("text") or "").split()
        pick = int(arg[1]) if len(arg) > 1 and arg[1].isdigit() else None

        try:
            folders = await eventscan.list_folders(acc_id)
        except Exception as e:  # noqa: BLE001
            await self.send_notification(chat_id, f"Papkalarni o'qib bo'lmadi: {e}")
            return

        if not folders:
            await self.send_notification(
                chat_id,
                "Kanal/guruhli papka topilmadi. Telegram'da papka yarating "
                "(Sozlamalar → Papkalar) va unga kanallar/guruhlarni qo'shing.",
            )
            return

        # Papka tanlash: /events <raqam> yoki saqlangan config
        folder_id = None
        if pick is not None:
            if not (1 <= pick <= len(folders)):
                folder_id = None
            else:
                folder_id = folders[pick - 1]["id"]
        elif config and config.folder_id:
            folder_id = config.folder_id

        if folder_id is None:
            lines = ["Qaysi papkani tekshirishni tanlang:"]
            for i, f in enumerate(folders, 1):
                lines.append(f"{i}. {f['title']} ({f['peers']} kanal/guruh)")
            lines.append("")
            lines.append("Javob: /events <raqam>   (masalan: /events 1)")
            lines.append("Yoki ilovada 'Tadbirlar' bo'limidan tanlang.")
            await self.send_notification(chat_id, "\n".join(lines))
            return

        # Saqlangan config (kun/qo'shimcha kalit so'z)
        days = config.days if config else 7
        extra = config.extra_keywords if config else ""

        await self.send_notification(chat_id, "Tekshirilmoqda… (bu biroz vaqt olishi mumkin)")
        try:
            result = await eventscan.scan_folder(acc_id, folder_id, days=days, extra_keywords=extra)
        except Exception as e:  # noqa: BLE001
            await self.send_notification(chat_id, f"Skanerlab bo'lmadi: {e}")
            return

        # Natijani DB'ga saqlaymiz (ilova ham bir xil so'nggi natijani ko'radi).
        # Config ham shu bitta chaqiruvda yangilanadi — ikki marta yozilmaydi.
        try:
            await eventscan.persist_events(
                acc_id,
                result["events"],
                result.get("folder_title", ""),
                result.get("days", days),
                folder_id=folder_id,
                extra_keywords=extra,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Event'larni saqlashda xato: %s", e)

        events = result["events"]
        scanned = result["scanned"]
        folder_title = result.get("folder_title", "")
        if not events:
            await self.send_notification(
                chat_id,
                f"'{folder_title}' papkasida {scanned} ta kanal/guruh tekshirildi "
                f"(so'nggi {result.get('days', days)} kun) — tadbir topilmadi.",
            )
            return

        # Jadval ko'rinishida (Telegram matn) — 4096 belgi chegarasiga bo'lib yuboramiz
        head = (
            f"Tadbirlar — '{folder_title}'\n"
            f"{scanned} kanal/guruh · so'nggi {result.get('days', days)} kun · {len(events)} ta topildi\n"
            "──────────────"
        )
        chunks = [head]
        cur = head
        for i, ev in enumerate(events[:15], 1):
            block = [f"\n{i}. {ev['name']}"]
            if ev.get("when"):
                block.append(f"   Vaqt: {ev['when']}")
            if ev.get("place"):
                block.append(f"   Joy: {ev['place']}")
            if ev.get("purpose"):
                block.append(f"   Maqsad: {ev['purpose'][:140]}")
            block.append(f"   Manba: {ev.get('source_title', '')}")
            text = "\n".join(block)
            if len(cur) + len(text) > 3800:
                chunks.append(text)
                cur = text
            else:
                cur += "\n" + text
        for c in chunks:
            await self.send_notification(chat_id, c)

    async def _cmd_music(self, chat_id: int) -> None:
        from sqlalchemy import select

        from .db import MusicPost, SessionLocal

        async with SessionLocal() as db:
            rows = (
                await db.execute(select(MusicPost).order_by(MusicPost.created_at.desc()).limit(15))
            ).scalars().all()
        if not rows:
            await self.send_notification(chat_id, "Musiqalar hozircha yo'q.")
            return
        lines = ["Musiqalar:"]
        for i, p in enumerate(rows, 1):
            line = f"{i}. {p.title}"
            if p.performer:
                line += f" — {p.performer}"
            lines.append(line)
        await self.send_notification(chat_id, "\n".join(lines))

    async def _cmd_autoreply(self, chat_id: int, msg: dict | None) -> None:
        from sqlalchemy import select

        from .db import Account, AppUser, SessionLocal

        arg = (msg.get("text") or "").split()
        async with SessionLocal() as db:
            acc = (
                await db.execute(select(Account).where(Account.auth_step == "ready").limit(1))
            ).scalar_one_or_none()
            if acc is None:
                await self.send_notification(chat_id, "Akkaunt topilmadi.")
                return
            u = (
                await db.execute(select(AppUser).where(AppUser.account_id == acc.id))
            ).scalar_one_or_none()
            if u is None:
                u = AppUser(account_id=acc.id)
                db.add(u)
            if len(arg) > 1 and arg[1].lower() in ("on", "off", "yoqish", "o'chirish"):
                u.auto_reply_enabled = arg[1].lower() in ("on", "yoqish")
            else:
                u.auto_reply_enabled = not u.auto_reply_enabled
            state = u.auto_reply_enabled
            await db.commit()
        await self.send_notification(
            chat_id,
            f"Avto-javob: {'YOQILGAN' if state else 'O\'CHIRILGAN'}.",
        )

    async def _cmd_users(self, chat_id: int) -> None:
        from sqlalchemy import select

        from .db import Account, AppUser, SessionLocal

        async with SessionLocal() as db:
            accounts = (await db.execute(select(Account))).scalars().all()
            users = {u.account_id: u for u in (await db.execute(select(AppUser))).scalars().all()}
        lines = ["Foydalanuvchilar:"]
        for a in accounts:
            u = users.get(a.id)
            tag = "OWNER" if (u and u.is_owner) else ("VIP" if (u and u.is_vip) else "")
            name = a.bot_name or a.first_name or a.phone
            lines.append(f"{a.id}. {name} ({a.phone}) {tag}".strip())
        await self.send_notification(chat_id, "\n".join(lines))

    async def _cmd_vip(self, chat_id: int, msg: dict | None) -> None:
        from sqlalchemy import select

        from .db import AppUser, SessionLocal

        parts = (msg.get("text") or "").split()
        if len(parts) < 2 or not parts[1].isdigit():
            await self.send_notification(chat_id, "Ishlatish: /vip <foydalanuvchi id>")
            return
        acc_id = int(parts[1])
        async with SessionLocal() as db:
            u = (
                await db.execute(select(AppUser).where(AppUser.account_id == acc_id))
            ).scalar_one_or_none()
            if u is None:
                await self.send_notification(chat_id, f"{acc_id} id'li foydalanuvchi topilmadi.")
                return
            u.is_vip = not u.is_vip
            state = u.is_vip
            await db.commit()
        await self.send_notification(
            chat_id,
            f"{acc_id} id'li foydalanuvchi {'VIP qilindi' if state else 'VIP dan olindi'}.",
        )

    async def _cmd_report(self, chat_id: int) -> None:
        from sqlalchemy import select

        from .db import AdminReport, SessionLocal

        async with SessionLocal() as db:
            rows = (
                await db.execute(select(AdminReport).order_by(AdminReport.created_at.desc()).limit(3))
            ).scalars().all()
        if not rows:
            await self.send_notification(chat_id, "AI hisobotlar hozircha yo'q.")
            return
        for r in rows:
            body = r.body[:4000]
            await self.send_notification(chat_id, body)

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

    # ---------------- bot ichida javob berish ----------------
    async def save_reply_ctx(
        self,
        bot_message_id: int,
        *,
        scope: str,
        account_id: int | None = None,
        dialog_id: int | None = None,
        msg_tg_id: int | None = None,
        delegate_dialog_id: int | None = None,
    ) -> None:
        """Xabarnoma message_id'sini dialogga bog'laydi — reply qilinsa shu yerga boradi."""
        if bot_message_id is None:
            return
        from sqlalchemy import delete  # noqa: PLC0415

        from .db import BotReplyCtx, SessionLocal, utcnow  # noqa: PLC0415

        async with SessionLocal() as db:
            db.add(
                BotReplyCtx(
                    bot_message_id=bot_message_id,
                    scope=scope,
                    account_id=account_id,
                    dialog_id=dialog_id,
                    msg_tg_id=msg_tg_id,
                    delegate_dialog_id=delegate_dialog_id,
                )
            )
            # Vaqti-vaqti bilan eski kontekstlarni tozalab turamiz
            if bot_message_id % 50 == 0:
                await db.execute(
                    delete(BotReplyCtx).where(
                        BotReplyCtx.created_at < utcnow() - timedelta(days=30)
                    )
                )
            await db.commit()

    async def get_reply_ctx(self, bot_message_id: int) -> dict | None:
        from sqlalchemy import select  # noqa: PLC0415

        from .db import BotReplyCtx, SessionLocal  # noqa: PLC0415

        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(BotReplyCtx).where(BotReplyCtx.bot_message_id == bot_message_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "scope": row.scope,
                "account_id": row.account_id,
                "dialog_id": row.dialog_id,
                "msg_tg_id": row.msg_tg_id,
                "delegate_dialog_id": row.delegate_dialog_id,
            }

    async def _handle_reply_in_bot(self, msg: dict) -> bool:
        """Egasi bot ichida xabarnomaga reply yozdi — javobni aynan shu chatga yetkazamiz.

        Saytga yo'naltirmaydi: javob to'g'ridan-to'g'ri Telegram ichida beriladi.
        """
        reply = msg.get("reply_to_message") or {}
        reply_id = reply.get("message_id")
        if not reply_id:
            return False
        ctx = await self.get_reply_ctx(reply_id)
        if ctx is None:
            return False

        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or msg.get("caption") or "").strip()
        media_type, file_id = media_info_of_bot_msg(msg)

        if not text and media_type == "none":
            await self.send_notification(chat_id, "Javob matnini yozing.")
            return True

        if ctx["scope"] == "delegate":
            ok = await self._send_to_delegate(ctx["delegate_dialog_id"], text, media_type, file_id)
        else:
            ok = await self._send_to_chat(ctx, text, media_type, file_id)

        if ok:
            await self.send_notification(
                chat_id, "Yuborildi", reply_to_message_id=msg["message_id"]
            )
        else:
            await self.send_notification(
                chat_id,
                "Yuborilmadi. Akkaunt Telegram'ga ulanganligini tekshiring (/status).",
                reply_to_message_id=msg["message_id"],
            )
        return True

    async def _send_to_delegate(
        self, delegate_dialog_id: int | None, text: str, media_type: str, file_id: str | None
    ) -> bool:
        from sqlalchemy import select  # noqa: PLC0415

        from .db import DelegateDialog, DelegateMessage, SessionLocal, utcnow  # noqa: PLC0415
        from .ws import ws_manager  # noqa: PLC0415

        if delegate_dialog_id is None:
            return False
        async with SessionLocal() as db:
            dlg = (
                await db.execute(select(DelegateDialog).where(DelegateDialog.id == delegate_dialog_id))
            ).scalar_one_or_none()
            if dlg is None:
                return False
            if media_type != "none" and file_id:
                sent = await self.send_media(dlg.bot_chat_id, file_id, media_type, text)
            else:
                sent = await self.send_text(dlg.bot_chat_id, text)
            if not sent:
                return False
            out = DelegateMessage(
                dialog_id=dlg.id, direction="out", text=text, media_type=media_type, file_id=file_id
            )
            db.add(out)
            dlg.last_msg_text = text or (media_type if media_type != "none" else "")
            dlg.last_msg_date = utcnow()
            dlg.last_out = True
            await db.flush()
            serialized_dlg = _serialize_delegate_dialog(dlg)
            serialized_msg = _serialize_delegate_message(out)
            await db.commit()

        owner_acc = await _owner_account_id()
        if owner_acc is not None:
            await ws_manager.broadcast(
                owner_acc,
                {"type": "delegate_message", "dialog": serialized_dlg, "message": serialized_msg},
            )
        return True

    async def _send_to_chat(
        self, ctx: dict, text: str, media_type: str, file_id: str | None
    ) -> bool:
        """Oddiy (akkaunt) chatga MTProto orqali javob yuboradi."""
        from . import actions  # noqa: PLC0415
        from .storage import storage  # noqa: PLC0415

        account_id = ctx.get("account_id")
        dialog_id = ctx.get("dialog_id")
        if not account_id or not dialog_id:
            return False
        try:
            if media_type != "none" and file_id:
                data = await self.get_file(file_id)
                if not data:
                    return False
                ext = _ext_for(media_type)
                key = storage.put(data, _mime_for(media_type), ext)
                await actions.send_media(
                    account_id,
                    dialog_id,
                    key,
                    media_type,
                    caption=text,
                    reply_to_tg_id=ctx.get("msg_tg_id"),
                )
            else:
                await actions.send_text(account_id, dialog_id, text, ctx.get("msg_tg_id"))
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Bot ichidan chatga yuborishda xato: %s", e)
            return False

    async def _cmd_reply(self, chat_id: int, msg: dict) -> None:
        """/r <raqam|@username> matn — bot ichidan begonaga javob."""
        from sqlalchemy import select  # noqa: PLC0415

        from .db import DelegateDialog, SessionLocal  # noqa: PLC0415

        raw = (msg.get("text") or "").split()
        if len(raw) < 2:
            await self.send_notification(chat_id, "Ishlatish: /r <raqam> matn  (masalan: /r 1 salom)")
            return
        target, body = raw[1], " ".join(raw[2:]).strip()
        async with SessionLocal() as db:
            if target.isdigit():
                rows = (
                    await db.execute(
                        select(DelegateDialog)
                        .order_by(DelegateDialog.last_msg_date.desc().nullslast())
                        .limit(15)
                    )
                ).scalars().all()
                idx = int(target) - 1
                if not (0 <= idx < len(rows)):
                    await self.send_notification(chat_id, "Bunday raqam yo'q. /list bilan tekshiring.")
                    return
                dlg = rows[idx]
            else:
                username = target.lstrip("@")
                dlg = (
                    await db.execute(
                        select(DelegateDialog).where(DelegateDialog.username == username)
                    )
                ).scalar_one_or_none()
                if dlg is None:
                    await self.send_notification(chat_id, f"@{username} topilmadi. /list bilan tekshiring.")
                    return
            dlg_id = dlg.id
            name = dlg.first_name or dlg.username or "Foydalanuvchi"
        if not body:
            await self.send_notification(chat_id, "Javob matnini yozing: /r 1 salom")
            return
        ok = await self._send_to_delegate(dlg_id, body, "none", None)
        await self.send_notification(chat_id, f"{name} ga yuborildi" if ok else "Yuborilmadi")

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
            is_new = False
            if dlg is None:
                dlg = DelegateDialog(bot_chat_id=chat_id, first_name=name, username=username)
                db.add(dlg)
                await db.flush()
                is_new = True
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

        # Bot ichida javob berish: forward qilingan xabar → kontekst.
        # Egasi shu xabarga reply yozsa, javob begonaga bot nomidan boradi (saytga yo'naltirmaydi).
        if notif_id:
            await self.save_reply_ctx(
                notif_id, scope="delegate", delegate_dialog_id=dlg.id
            )
            if is_new:
                who = name or (f"@{username}" if username else "Foydalanuvchi")
                await self.send_notification(
                    self.owner_id,
                    f"{who} yozdi. Javobni shu yerda yozing — xabar bot nomidan yetkaziladi.",
                    force_reply=True,
                    placeholder="Javobingizni yozing…",
                    reply_to_message_id=notif_id,
                )

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
    from .security import sign_media_url
    from .storage import storage

    media_url = None
    if m.media_key and storage.exists(m.media_key):
        media_url = storage.url(m.media_key)
    elif m.media_type != "none" and getattr(m, "file_id", None):
        media_url = sign_media_url(f"/api/delegate/media/{m.id}")
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
