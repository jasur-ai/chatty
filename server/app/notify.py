"""Telegram Bot API orqali xabarnomalar.

App ochiq bo'lmaganda, bot odamlarga xabarlar kelganda egasiga push yuboradi:
  - "3:21 min audio"
  - "Matn: salom ..."
  - "Rasm"
va ostida **Javob yozish** tugmasi (Chatty app'ni ochadi).
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


class BotNotifier:
    def __init__(self) -> None:
        self.token = settings.tg_bot_token
        self.enabled = bool(self.token)
        self._offset = 0
        self._task: asyncio.Task | None = None

    @property
    def base(self) -> str:
        return f"{API}/bot{self.token}"

    async def get_me(self) -> dict | None:
        if not self.enabled:
            return None
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base}/getMe", timeout=10)
            return r.json().get("result")

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
        try:
            async with httpx.AsyncClient() as c:
                r = await c.post(f"{self.base}/sendMessage", json=payload, timeout=15)
            return bool(r.json().get("ok"))
        except Exception as e:  # noqa: BLE001
            log.warning("Xabarnoma yuborilmadi: %s", e)
            return False

    # ---------------- polling (callback tugmalar + /start) ----------------
    async def start_polling(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._poll_loop())
        asyncio.create_task(self._setup_commands())
        log.info("Bot polling boshlandi (@chattiey_bot)")

    async def _setup_commands(self) -> None:
        """Bot menyusiga komandalarni qo'shadi (Telegram'da '/' bosilganda ko'rinadi)."""
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
        elif "message" in upd:
            msg = upd["message"]
            chat_id = msg["chat"]["id"]
            text = (msg.get("text") or "").strip()
            cmd = text.split()[0].split("@")[0] if text.startswith("/") else text
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


notifier = BotNotifier()