"""Lotus 0.0.1 — o'rnatilgan AI yordamchi (Jarvis uslubida).

Xususiyatlari:
  - Til: uz (default) / ru / en
  - Real LLM (tekin provider: Groq/OpenRouter/Gemini) faqat VIP foydalanuvchilarga.
    Oddiy foydalanuvchilar uchun o'rnatilgan offline intents ishlaydi (kalitsiz).
  - Eslatmalar (reminders), yordam, til almashtirish, hisobot va boshqa buyruqlar.
  - Voice chat: STT/TTS uchun hook'lar (frontend brauzer STT, TTS esa xizmat orqali).
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

log = logging.getLogger("chatty.lotus")

LOTUS_NAME = "Lotus 0.0.1"
LANGUAGES = {"uz", "ru", "en"}

# Tein LLM sozlamalari (ixtiyoriy — faqat VIP uchun)
LLM_URL = settings.lotus_endpoint
LLM_KEY = settings.lotus_llm_key
LLM_MODEL = settings.lotus_llm_model

_INTRO = {
    "uz": "Salom, men Lotus 0.0.1 — sizning shaxsiy yordamchingizman. "
          "Eslatma qo'yish, chatlarni boshqarish, savollarga javob berish va "
          "boshqa ko'p narsada yordam bera olaman. 'Yordam' deb yozing.",
    "ru": "Здравствуйте, я Lotus 0.0.1 — ваш личный помощник. "
          "Могу поставить напоминание, управлять чатами, отвечать на вопросы. Напишите 'Помощь'.",
    "en": "Hello, I'm Lotus 0.0.1 — your personal assistant. "
          "I can set reminders, manage chats, answer questions and more. Type 'help'.",
}

_HELP = {
    "uz": "Mening buyruqlarim:\n"
          "- 'Eslatma: <matn> <vaqtda>' — eslatma qo'yish (masalan: 'Eslatma: qo'ng'iroq qil 15:00 da')\n"
          "- 'Eslatmalarim' — eslatmalar ro'yxati\n"
          "- 'Til: ru/uz/en' — tilni o'zgartirish\n"
          "- 'Hisobot' — umumiy holat haqida qisqacha hisobot\n"
          "- 'Yordam' — shu ro'yxat",
    "ru": "Мои команды:\n"
          "- 'Напоминание: <текст> <время>' — поставить напоминание\n"
          "- 'Мои напоминания' — список напоминаний\n"
          "- 'Язык: ru/uz/en' — сменить язык\n"
          "- 'Отчёт' — краткий отчёт\n"
          "- 'Помощь' — этот список",
    "en": "My commands:\n"
          "- 'Remind: <text> at <time>' — set a reminder\n"
          "- 'My reminders' — list reminders\n"
          "- 'Language: ru/uz/en' — change language\n"
          "- 'Report' — brief status report\n"
          "- 'Help' — this list",
}

_YES = {"uz": "ha", "ru": "да", "en": "yes"}


async def is_vip(account_id: int | None) -> bool:
    """Foydalanuvchi VIP ekanini tekshiradi (LLM faqat VIP uchun)."""
    if account_id is None:
        return False
    from sqlalchemy import select  # noqa: PLC0415

    from .db import AppUser, SessionLocal  # noqa: PLC0415

    async with SessionLocal() as db:
        u = (
            await db.execute(select(AppUser).where(AppUser.account_id == account_id))
        ).scalar_one_or_none()
        return bool(u and u.is_vip)


class Lotus:
    def __init__(self) -> None:
        self.language = "uz"
        self.voice_enabled = False
        self.llm_enabled = bool(LLM_URL and LLM_KEY)

    # ---------- tashqi sozlamalar (DB'dan yuklanadi) ----------
    def configure(self, language: str | None = None, voice_enabled: bool | None = None) -> None:
        if language in LANGUAGES:
            self.language = language
        if voice_enabled is not None:
            self.voice_enabled = voice_enabled

    # ---------- LLM ----------
    async def _llm(self, messages: list[dict]) -> str | None:
        if not self.llm_enabled:
            return None
        try:
            headers = {"Content-Type": "application/json"}
            if LLM_KEY:
                headers["Authorization"] = f"Bearer {LLM_KEY}"
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    LLM_URL,
                    json={"model": LLM_MODEL, "messages": messages},
                    headers=headers,
                )
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            log.warning("LLM xatosi (offline'ga tushamiz): %s", e)
            return None

    # ---------- buyruqni tahlil qilish (offline intents) ----------
    async def reply(self, text: str, context: dict | None = None) -> str:
        """Foydalanuvchi matniga javob beradi (VIP -> LLM, oddiy -> offline)."""
        text = (text or "").strip()
        lang = self.language
        account_id = (context or {}).get("account_id")

        # 1) buyruqlar (barcha tillarda)
        low = text.lower()

        if any(k in low for k in ("eslatma", "напомин", "remind", "reminder")):
            return await self._handle_reminder(text, lang)
        if any(k in low for k in ("eslatmalarim", "мои напоминания", "my reminders")):
            from .scheduler import list_reminders_text  # noqa: PLC0415
            return await list_reminders_text(lang)

        if low.startswith(("til", "язык", "language", "lang")):
            for code in LANGUAGES:
                if code in low:
                    self.language = code
                    return {
                        "uz": f"Til {code.upper()} ga o'zgartirildi.",
                        "ru": f"Язык изменён на {code.upper()}.",
                        "en": f"Language changed to {code.upper()}.",
                    }[code]

        if any(k in low for k in ("hisobot", "отчёт", "report")):
            from .scheduler import build_report_text  # noqa: PLC0415
            return await build_report_text(lang)

        if any(k in low for k in ("yordam", "помощь", "help", "nima qila olasan", "что умеешь")):
            return _HELP.get(lang, _HELP["uz"])

        if any(k in low for k in ("salom", "assalom", "привет", "здравств", "hello", "hi")):
            return _INTRO.get(lang, _INTRO["uz"])

        # 2) LLM (faqat VIP foydalanuvchilar uchun, agar kalit sozlangan bo'lsa)
        if self.llm_enabled and await is_vip(account_id):
            sys_msg = {
                "uz": "Sen Lotus 0.0.1, Chatty platformasining ichki yordamchisisan. Qisqa va aniq javob ber.",
                "ru": "Ты Lotus 0.0.1, внутренний помощник платформы Chatty. Отвечай кратко и точно.",
                "en": "You are Lotus 0.0.1, the internal assistant of Chatty. Answer briefly and accurately.",
            }[lang]
            llm_out = await self._llm(
                [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": text},
                ]
            )
            if llm_out:
                return llm_out

        # 3) offline fallback
        return {
            "uz": "Tushunmadim. 'Yordam' deb yozsangiz, nima qila olishimni ko'rsataman.",
            "ru": "Не понял. Напишите 'Помощь', и я покажу, что умею.",
            "en": "I didn't understand. Type 'help' to see what I can do.",
        }[lang]

    async def _handle_reminder(self, text: str, lang: str) -> str:
        """'Eslatma: <matn> <vaqt>' formatini tahlil qilib eslatma qo'yadi."""
        import re  # noqa: PLC0415

        body = re.sub(r"(?i)(eslatma|напомин|remind|reminder)\s*[:：]\s*", "", text)
        # Vaqtni topish: HH:MM yoki HH soat MM daqiqa
        m = re.search(r"(\d{1,2})[:.](\d{2})\b", body)
        if not m:
            m = re.search(r"(\d{1,2})\s*(soat|час|hour)", body)
            if not m:
                return {
                    "uz": "Eslatma vaqtini ko'rsating, masalan: 'Eslatma: qo'ng'iroq qil 15:00'",
                    "ru": "Укажите время, например: 'Напоминание: позвонить в 15:00'",
                    "en": "Specify a time, e.g. 'Remind: call at 15:00'",
                }[lang]
            hour = int(m.group(1))
            minute = 0
        else:
            hour, minute = int(m.group(1)), int(m.group(2))

        task = re.sub(r"\b\d{1,2}[:.]\d{2}\b|\d{1,2}\s*(soat|час|hour)\b", "", body, flags=re.I).strip(" :,-")

        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return {
                "uz": "Vaqt noto'g'ri (00:00-23:59 oralig'ida bo'lishi kerak).",
                "ru": "Неверное время (должно быть в пределах 00:00-23:59).",
                "en": "Invalid time (must be within 00:00-23:59).",
            }[lang]

        from .scheduler import add_reminder  # noqa: PLC0415
        due = datetime.now(timezone.utc).replace(minute=minute, second=0, microsecond=0)
        # soat o'tib ketgan bo'lsa ertaga
        now = datetime.now(timezone.utc)
        candidate = due.replace(hour=hour)
        if candidate <= now:
            candidate += timedelta(days=1)
        await add_reminder(task or "Eslatma", candidate)

        t = candidate.strftime("%H:%M")
        return {
            "uz": f"Eslatma qo'yildi: '{task or 'Eslatma'}' — {t} da eslatib turaman.",
            "ru": f"Напоминание установлено: '{task or 'Напоминание'}' — в {t}.",
            "en": f"Reminder set: '{task or 'Reminder'}' at {t}.",
        }[lang]

    async def generate(self, prompt: str, account_id: int | None = None) -> str | None:
        """Umumiy LLM chaqiruv (faqat VIP uchun). Javob yo'q bo'lsa None."""
        if not (self.llm_enabled and await is_vip(account_id)):
            return None
        return await self._llm(
            [
                {
                    "role": "system",
                    "content": "Sen Lotus 0.0.1, Chatty platformasining ichki yordamchisisan.",
                },
                {"role": "user", "content": prompt},
            ]
        )

    async def summarize(self, text: str, account_id: int | None = None) -> str | None:
        """Matnni xulosa qilish (VIP)."""
        return await self.generate(f"Quyidagi matnni 2-3 jumlada xulosa qil:\n\n{text}", account_id)

    async def translate(self, text: str, target: str, account_id: int | None = None) -> str | None:
        """Tarjima (VIP). target: uz/ru/en."""
        names = {"uz": "o'zbek", "ru": "rus", "en": "ingliz"}
        return await self.generate(
            f"Quyidagi matnni {names.get(target, target)} tiliga tarjima qil, faqat tarjimani qaytar:\n\n{text}",
            account_id,
        )

    async def ai_reply_text(self, incoming: str, account_id: int | None = None) -> str | None:
        """Kiruvchi xabarga kontekstli AI javob (VIP uchun avto-javob)."""
        return await self.generate(
            "Sen ushbu akkaunt egasisan. Quyidagi xabarga qisqa, tabiiy va do'stona javob yoz "
            "(o'zbek tilida, 1-2 jumla):\n\n" + incoming,
            account_id,
        )

    async def ask_confirm(self, text: str) -> bool:
        """Tasdiqlash so'roviga javob beradi (ha/yo'q)."""
        low = (text or "").lower()
        yes_words = {"ha", "haa", "ho", "ok", "yes", "да", "ага", "yep", "bo'ladi", "буде"}
        return any(w in low.split() for w in yes_words)


lotus = Lotus()
