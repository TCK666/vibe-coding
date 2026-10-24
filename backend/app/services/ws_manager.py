"""会话级 WebSocket 连接注册表：连接维护与广播推送。"""
import asyncio
import json
import time

from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self._conns: dict[int, set[WebSocket]] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, conversation_id: int) -> asyncio.Lock:
        if conversation_id not in self._locks:
            self._locks[conversation_id] = asyncio.Lock()
        return self._locks[conversation_id]

    async def connect(self, conversation_id: int, ws: WebSocket) -> None:
        # accept 由调用方（端点）负责，这里只注册
        self._conns.setdefault(conversation_id, set()).add(ws)

    def disconnect(self, conversation_id: int, ws: WebSocket) -> None:
        self._conns.get(conversation_id, set()).discard(ws)
        if not self._conns.get(conversation_id):
            self._conns.pop(conversation_id, None)
            self._locks.pop(conversation_id, None)

    async def _send(self, ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            pass  # 单连接失效不影响广播

    async def broadcast(self, conversation_id: int, msg_type: str, data: dict) -> None:
        payload = {"type": msg_type, "data": data, "ts": int(time.time() * 1000)}
        conns = list(self._conns.get(conversation_id, set()))
        if not conns:
            return
        async with self._lock(conversation_id):
            for ws in conns:
                await self._send(ws, payload)

    def has_connection(self, conversation_id: int) -> bool:
        return bool(self._conns.get(conversation_id))


ws_manager = WSManager()
