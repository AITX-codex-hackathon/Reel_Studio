"""Serve uploaded and generated images directly (used by the frontend for previews)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..storage import UploadRow, get_db

router = APIRouter(tags=["files"])


@router.get("/uploads/{upload_id}/file")
def get_upload_file(upload_id: str, db: Session = Depends(get_db)) -> FileResponse:
    row = db.get(UploadRow, upload_id)
    if not row:
        raise HTTPException(404, "Upload not found")
    p = Path(row.path)
    if not p.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(path=str(p))
