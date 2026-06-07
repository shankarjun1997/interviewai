"""In-memory WebSocket room manager for live interview sessions.

One room per session_id; interviewer clients join and receive broadcast events
(transcript segments, copilot hints). Single-instance only — for multi-instance
deployment, back this with Redis pub/sub (follow-up).
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[session_id].add(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        self._rooms[session_id].discard(ws)
        if not self._rooms[session_id]:
            self._rooms.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._rooms.get(session_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    def room_size(self, session_id: str) -> int:
        return len(self._rooms.get(session_id, set()))


manager = ConnectionManager()
