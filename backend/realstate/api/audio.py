"""Audio library + serving."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..integrations.stock_audio import StockAudioLibrary

router = APIRouter(prefix="/audio", tags=["audio"])

_lib = StockAudioLibrary()


class TrackOut(BaseModel):
    name: str
    relative_path: str
    mood: Optional[str] = None
    tempo: Optional[str] = None
    tags: list[str] = []


@router.get("", response_model=list[TrackOut])
def list_tracks() -> list[TrackOut]:
    tracks = _lib.scan()
    out = []
    for t in tracks:
        try:
            rel = t.path.relative_to(_lib.root)
        except ValueError:
            rel = Path(t.path.name)
        out.append(
            TrackOut(
                name=t.name,
                relative_path=str(rel),
                mood=t.mood,
                tempo=t.tempo,
                tags=list(t.tags),
            )
        )
    return out


@router.get("/file/{relative_path:path}")
def get_track_file(relative_path: str) -> FileResponse:
    candidate = (_lib.root / relative_path).resolve()
    root = _lib.root.resolve()
    # Security: refuse anything that escapes the library root
    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(400, "Invalid path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(404, "Track not found")
    return FileResponse(path=str(candidate))
