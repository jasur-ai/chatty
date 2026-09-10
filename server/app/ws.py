"""WebSocket connection manager — har bir akkaunt uchun real-time event push."""
from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, account_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.setdefault(account_id, set()).add(ws)

    def disconnect(self, account_id: int, ws: WebSocket) -> None:
        self.connections.get(account_id, set()).discard(ws)

    async def broadcast(self, account_id: int, event: dict) -> None:
        for ws in list(self.connections.get(account_id, set())):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(account_id, ws)


ws_manager = WSManager()