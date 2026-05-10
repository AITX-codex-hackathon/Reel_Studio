"""Image upload + listing."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from ..models.project import ImageAnalysis, Upload
from ..storage import AnalysisRow, ProjectRow, UploadRow, get_db
from ..storage.filesystem import ProjectFiles

router = APIRouter(prefix="/projects/{project_id}/uploads", tags=["uploads"])

_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
try:
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:
    pass


@router.post("", response_model=list[Upload])
async def upload_images(
    project_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[Upload]:
    project = db.get(ProjectRow, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    pf = ProjectFiles()
    out_dir = pf.uploads_dir(project_id)

    created: list[Upload] = []
    rejected: list[str] = []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in _ALLOWED_EXTS:
            rejected.append(f"{upload.filename or 'unnamed file'}: unsupported file type")
            continue

        # Compute sha256 + write file
        h = hashlib.sha256()
        upload_id = str(uuid.uuid4())
        out_path = out_dir / f"{upload_id}{suffix}"

        with open(out_path, "wb") as f:
            while chunk := await upload.read(1024 * 1024):
                h.update(chunk)
                f.write(chunk)

        sha = h.hexdigest()

        # Dedup by hash
        existing = db.query(UploadRow).filter_by(project_id=project_id, sha256=sha).first()
        if existing:
            out_path.unlink(missing_ok=True)
            created.append(Upload.model_validate(existing))
            continue

        # Read dims
        try:
            with Image.open(out_path) as im:
                w, h_px = im.size
        except Exception:
            out_path.unlink(missing_ok=True)
            rejected.append(f"{upload.filename or out_path.name}: could not read image")
            continue

        row = UploadRow(
            id=upload_id,
            project_id=project_id,
            filename=upload.filename or out_path.name,
            path=str(out_path),
            width=w,
            height=h_px,
            sha256=sha,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        created.append(Upload.model_validate(row))

    db.commit()
    if not created and files:
        detail = (
            "No images were uploaded. Use JPG, PNG, WebP, or install HEIC support for iPhone HEIC files."
            if not rejected
            else "No images were uploaded. " + "; ".join(rejected[:3])
        )
        raise HTTPException(400, detail)
    return created


@router.get("", response_model=list[Upload])
def list_uploads(project_id: str, db: Session = Depends(get_db)) -> list[Upload]:
    rows = db.query(UploadRow).filter_by(project_id=project_id).order_by(UploadRow.created_at.asc()).all()
    return [Upload.model_validate(r) for r in rows]


@router.delete("/{upload_id}", status_code=204, response_class=Response)
def delete_upload(project_id: str, upload_id: str, db: Session = Depends(get_db)):
    row = db.query(UploadRow).filter_by(project_id=project_id, id=upload_id).first()
    if not row:
        raise HTTPException(404, "Upload not found")
    try:
        Path(row.path).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/{upload_id}/analysis", response_model=Optional[ImageAnalysis])
def get_analysis(project_id: str, upload_id: str, db: Session = Depends(get_db)) -> Optional[ImageAnalysis]:
    row = db.query(AnalysisRow).filter_by(upload_id=upload_id).first()
    if not row:
        return None
    return ImageAnalysis.model_validate(row)
