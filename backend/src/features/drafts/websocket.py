"""WebSocket manager for live draft broadcasts."""

from __future__ import annotations

import contextlib
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class DraftWSManager:
    """Manages WebSocket connections per draft, broadcasting events to all connected clients."""

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, draft_id: int, ws: WebSocket) -> None:
        await ws.accept()
        if draft_id not in self._connections:
            self._connections[draft_id] = []
        self._connections[draft_id].append(ws)
        # Notify the new client how many are online
        await ws.send_json(
            {
                "type": "connected",
                "participants_online": len(self._connections[draft_id]),
            }
        )
        # Notify others about new connection count
        await self._broadcast_online_count(draft_id)

    async def disconnect(self, draft_id: int, ws: WebSocket) -> None:
        if draft_id in self._connections:
            self._connections[draft_id] = [c for c in self._connections[draft_id] if c is not ws]
            if not self._connections[draft_id]:
                del self._connections[draft_id]
            else:
                await self._broadcast_online_count(draft_id)

    async def broadcast(self, draft_id: int, message: dict) -> None:
        """Send a message to all connected clients for a draft."""
        connections = self._connections.get(draft_id, [])
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            await self.disconnect(draft_id, ws)

    async def _broadcast_online_count(self, draft_id: int) -> None:
        count = len(self._connections.get(draft_id, []))
        connections = self._connections.get(draft_id, [])
        for ws in list(connections):
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "online_count", "participants_online": count})

    def get_online_count(self, draft_id: int) -> int:
        return len(self._connections.get(draft_id, []))


# Global singleton
draft_ws_manager = DraftWSManager()
