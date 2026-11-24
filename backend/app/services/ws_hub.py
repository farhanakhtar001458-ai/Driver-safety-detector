"""WebSocket connection manager with per-organisation rooms.

The simulator runs in a background thread; it enqueues payloads into a
thread-safe ``queue.Queue``. An asyncio consumer drains the queue and pushes to
connected clients, avoiding cross-thread asyncio calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
from collections import defaultdict
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self.user_sockets: dict[int, set[WebSocket]] = defaultdict(set)
        self._outbound: "queue.Queue[tuple[Optional[int], Any]]" = queue.Queue()
        self._consumer_started = False

    async def connect(self, websocket: WebSocket, organisation_id: int, user_id: int) -> None:
        await websocket.accept()
        self.rooms[organisation_id].add(websocket)
        self.user_sockets[user_id].add(websocket)
        await self.send_personal(websocket, {"type": "connection", "status": "connected"})

    def disconnect(self, websocket: WebSocket, organisation_id: int, user_id: int) -> None:
        self.rooms[organisation_id].discard(websocket)
        self.user_sockets[user_id].discard(websocket)

    async def send_personal(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            pass

    async def broadcast(self, organisation_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for websocket in list(self.rooms.get(organisation_id, set())):
            try:
                await websocket.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.rooms[organisation_id].discard(websocket)

    def publish(self, organisation_id: Optional[int], payload: dict[str, Any]) -> None:
        """Thread-safe publish from the simulator."""
        self._outbound.put((organisation_id, payload))

    async def consume(self) -> None:
        """Drain the outbound queue. Started once with the FastAPI lifespan."""
        while True:
            drained = 0
            try:
                while True:
                    organisation_id, payload = self._outbound.get_nowait()
                    if organisation_id is None:
                        for org_id in list(self.rooms.keys()):
                            await self.broadcast(org_id, payload)
                    else:
                        await self.broadcast(organisation_id, payload)
                    drained += 1
            except queue.Empty:
                pass
            await asyncio.sleep(0.05 if drained else 0.25)

    @property
    def connection_count(self) -> int:
        return sum(len(sockets) for sockets in self.rooms.values())

    def stats(self) -> dict[str, int]:
        return {"connections": self.connection_count, "organisations": len(self.rooms), "queued": self._outbound.qsize()}


manager = ConnectionManager()
