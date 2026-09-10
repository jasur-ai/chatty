"""Multi-account Telethon client registry."""
import asyncio
import logging

from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from ..config import settings
from ..db import Account, SessionLocal
from ..security import decrypt_session
from .events import on_message_read, on_new_message

log = logging.getLogger("chatty.manager")


class AccountManager:
    def __init__(self) -> None:
        self.clients: dict[int, TelegramClient] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        # login jarayonidagi vaqtinchalik clientlar: phone -> TelegramClient
        self.pending: dict[str, TelegramClient] = {}

    def lock(self, account_id: int) -> asyncio.Lock:
        return self.locks.setdefault(account_id, asyncio.Lock())

    def get(self, account_id: int) -> TelegramClient | None:
        return self.clients.get(account_id)

    async def start_all(self) -> None:
        """DB'dagi barcha tayyor akkauntlarni ulaydi (server ishga tushganda)."""
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Account).where(Account.auth_step == "ready", Account.is_active.is_(True))
                )
            ).scalars().all()
        for acc in rows:
            try:
                await self.start_account(acc)
            except Exception as e:  # noqa: BLE001 — bitta akkaunt xatosi boshqasini buzmasin
                log.warning("Akkaunt %s ulanishda xato: %s", acc.phone, e)

    async def start_account(self, acc: Account) -> TelegramClient | None:
        raw = decrypt_session(acc.session_enc)
        if not raw:
            log.warning("Akkaunt %s sessiyasi yo'q", acc.phone)
            return None

        api_id = acc.api_id or settings.tg_api_id
        api_hash = acc.api_hash or settings.tg_api_hash
        client = TelegramClient(StringSession(raw), api_id, api_hash)
        await client.connect()
        try:
            await client.get_me()
        except Exception as e:
            log.error("Akkaunt %s sessiyasi yaroqsiz: %s", acc.phone, e)
            await client.disconnect()
            return None

        client.add_event_handler(
            lambda ev: on_new_message(ev, account_id=acc.id), events.NewMessage
        )
        client.add_event_handler(
            lambda ev: on_message_read(ev, account_id=acc.id), events.MessageRead
        )
        old = self.clients.get(acc.id)
        if old:
            await old.disconnect()
        self.clients[acc.id] = client
        log.info("Akkaunt ulandi: %s (%s)", acc.first_name or acc.phone, acc.phone)
        return client

    async def stop_account(self, account_id: int) -> None:
        client = self.clients.pop(account_id, None)
        if client:
            await client.disconnect()

    async def shutdown(self) -> None:
        for client in list(self.clients.values()):
            await client.disconnect()
        for client in list(self.pending.values()):
            await client.disconnect()
        self.clients.clear()
        self.pending.clear()


manager = AccountManager()