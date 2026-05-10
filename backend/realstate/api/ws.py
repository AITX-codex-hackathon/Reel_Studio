"""WebSocket: per-project workflow progress channel."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


_clients: dict[str, set[WebSocket]] = defaultdict(set)
_latest_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
_lock = asyncio.Lock()
_MAX_EVENTS = 25


@router.get("/projects/{project_id}/workflow/current")
async def get_current_workflow(project_id: str) -> dict[str, Any]:
    """Return the latest workflow/render events for refresh/reconnect catch-up."""
    async with _lock:
        events = [dict(event) for event in _latest_events.get(project_id, [])]
        connected_clients = len(_clients.get(project_id, set()))
    return {"project_id": project_id, "connected_clients": connected_clients, "events": events}


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


async def broadcast_project_event(project_id: str, payload: dict[str, Any]) -> None:
    """Push a JSON payload to every client watching this project."""
    event = dict(payload)
    event.setdefault("type", "workflow")
    event.setdefault("created_at", time.time())
    async with _lock:
        _latest_events[project_id].insert(0, event)
        del _latest_events[project_id][_MAX_EVENTS:]
        clients = list(_clients.get(project_id, set()))
    dead: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    if dead:
        async with _lock:
            for ws in dead:
                _clients[project_id].discard(ws)


async def broadcast_workflow_status(
    project_id: str,
    *,
    stage: str,
    message: str,
    status: str = "running",
    progress: float | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": "workflow",
        "stage": stage,
        "status": status,
        "message": message,
    }
    if progress is not None:
        payload["progress"] = max(0.0, min(1.0, progress))
    if detail:
        payload.update(detail)
    await broadcast_project_event(project_id, payload)


async def broadcast_render_progress(project_id: str, payload: dict[str, Any]) -> None:
    payload.setdefault("type", "render")
    await broadcast_project_event(project_id, payload)
