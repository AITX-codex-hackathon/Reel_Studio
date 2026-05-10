"""WebSocket: per-project render progress channel."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


_clients: dict[str, set[WebSocket]] = defaultdict(set)
_lock = asyncio.Lock()


@router.websocket("/ws/projects/{project_id}/progress")
async def progress_ws(ws: WebSocket, project_id: str) -> None:
    await ws.accept()
    async with _lock:
        _clients[project_id].add(ws)
    try:
        while True:
            # Keep the socket open; we don't need messages from the client
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        async with _lock:
            _clients[project_id].discard(ws)


async def broadcast_render_progress(project_id: str, payload: dict[str, Any]) -> None:
    """Push a JSON payload to every client watching this project."""
    async with _lock:
        clients = list(_clients.get(project_id, set()))
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if dead:
        async with _lock:
            for ws in dead:
                _clients[project_id].discard(ws)
