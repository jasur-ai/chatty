"""Markaziy konfiguratsiya — .env faylidan o'qiladi."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # server/ .env


class Settings:
    # Telegram
    tg_api_id: int = int(os.getenv("TG_API_ID", "0"))
    tg_api_hash: str = os.getenv("TG_API_HASH", "")
    # Xabarnoma boti (Bot API) — push + "Javob yozish" tugmasi uchun
    tg_bot_token: str = os.getenv("TG_BOT_TOKEN", "")
    # "Javob yozish" tugmasi ochadigan URL (Chatty app)
    bot_reply_url: str = os.getenv("BOT_REPLY_URL", "")

    # Cloudflare R2 (S3-compatible)
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket: str = os.getenv("R2_BUCKET", "chatty-media")
    r2_endpoint: str = os.getenv(
        "R2_ENDPOINT", f"https://{os.getenv('R2_ACCOUNT_ID', '')}.r2.cloudflarestorage.com"
    )
    r2_public_url: str = os.getenv("R2_PUBLIC_URL", "")

    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    session_secret: str = os.getenv("SESSION_SECRET", "change-me")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")

    # Admin
    owner_id: int = int(os.getenv("OWNER_ID", "8004724563"))
    admin_ids: list[int] = [int(x) for x in os.getenv("ADMIN_IDS", "8442078631").split(",") if x]

    # Lotus AI (tekin LLM — VIP uchun; ixtiyoriy; bo'sh bo'lsa offline rejim)
    lotus_provider: str = os.getenv("LOTUS_PROVIDER", "groq")  # groq|openrouter|gemini|custom
    lotus_llm_url: str = os.getenv("LOTUS_LLM_URL", "")
    lotus_llm_key: str = os.getenv("LOTUS_LLM_KEY", "")
    lotus_llm_model: str = os.getenv("LOTUS_LLM_MODEL", "llama-3.3-70b-versatile")

    # Admin AI hisobot oraliq (soat) — 1/2/4/6/8
    report_interval_hours: int = int(os.getenv("REPORT_INTERVAL_HOURS", "2"))

    # LLM endpoint'ini provider preset bo'yicha avtomatik tanlash
    @property
    def lotus_endpoint(self) -> str:
        if self.lotus_llm_url:
            return self.lotus_llm_url
        presets = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        }
        return presets.get(self.lotus_provider, "https://api.groq.com/openai/v1/chat/completions")

    # DB
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/chatty.db")

    @property
    def r2_enabled(self) -> bool:
        return bool(self.r2_access_key_id and self.r2_secret_access_key and self.r2_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()