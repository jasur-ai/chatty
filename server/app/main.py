"""Chatty server — FastAPI ilovasi."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import admin, auth, bot, chats, lotus_api, vip
from .config import settings
from .db import init_db
from .notify import notifier
from .scheduler import scheduler
from .security import decode_token
from .tg.manager import manager
from .ws import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("chatty")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await manager.start_all()
    await notifier.start_polling()
    await scheduler.start()
    log.info("Chatty server ishga tushdi")
    yield
    await scheduler.stop()
    await notifier.stop()
    await manager.shutdown()


app = FastAPI(title="Chatty", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev uchun; prod'da toraytiriladi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(admin.router)
app.include_router(bot.router)
app.include_router(lotus_api.router)
app.include_router(vip.router)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "accounts_online": len(manager.clients),
        "bot_enabled": notifier.enabled,
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = ws.query_params.get("token", "")
    account_id = decode_token(token)
    if account_id is None:
        await ws.close(code=4401)
        return
    await ws_manager.connect(account_id, ws)
    try:
        while True:
            await ws.receive_text()  # keepalive: client ping yuborib turadi
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(account_id, ws)


# Prod'da web build'ini xizmat qilish (web/dist mavjud bo'lsa)
# Docker'da web/dist /app/web/dist; lokalda repo/web/dist — ikkalasini ham tekshiramiz.
import os

_env_dist = os.getenv("WEB_DIST", "")
_web_dist_candidates = [
    Path(__file__).resolve().parent.parent.parent / "web" / "dist",  # lokal: <repo>/web/dist
    Path(__file__).resolve().parent.parent / "web" / "dist",  # docker: /app/web/dist
]
if _env_dist:
    _web_dist_candidates.insert(0, Path(_env_dist))
_web_dist = next((p for p in _web_dist_candidates if p.exists()), None)
if _web_dist:
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")