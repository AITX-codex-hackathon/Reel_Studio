"""Storyboard generation + retrieval."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents.image_analyzer import ImageAnalysisResult
from ..models.project import Project
from ..models.storyboard import Storyboard
from ..services import StoryboardBuilder
from ..storage import AnalysisRow, ProjectRow, StoryboardRow, UploadRow, get_db
from ..storage.filesystem import TemplateLoader

router = APIRouter(prefix="/projects/{project_id}/storyboard", tags=["storyboards"])

_loader = TemplateLoader()


class GenerateBody(BaseModel):
    template_id: str
    use_audio_for_pacing: bool = False


@router.post("", response_model=Storyboard)
async def generate_storyboard(
    project_id: str,
    body: GenerateBody,
    db: Session = Depends(get_db),
) -> Storyboard:
    project_row = db.get(ProjectRow, project_id)
    if not project_row:
        raise HTTPException(404, "Project not found")

    template = _loader.get(body.template_id)
    if not template:
        raise HTTPException(404, f"Template {body.template_id} not found")

    upload_rows = db.query(UploadRow).filter_by(project_id=project_id).all()
    if not upload_rows:
        raise HTTPException(400, "Upload some images first")

    # Collect analyzed uploads (cached or fresh)
    uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]] = []
    for u in upload_rows:
        a = db.query(AnalysisRow).filter_by(upload_id=u.id).first()
        cached = None
        if a:
            cached = ImageAnalysisResult(
                room_type=a.room_type,
                quality_score=a.quality_score,
                framing=a.framing,
                lighting=a.lighting,
                dominant_colors=list(a.dominant_colors or []),
                suggested_motion=a.suggested_motion,
                notes=a.notes,
                raw=dict(a.raw or {}),
            )
        uploads.append((u.id, Path(u.path), cached))

    builder = StoryboardBuilder()
    storyboard = await builder.build(
        project=Project.model_validate(project_row),
        template=template,
        uploads=uploads,
        audio_path_for_pacing=None,  # v1: pacing analyzed against shot music after we know it
    )

    # Persist any newly computed analyses
    for upload_id, _, _ in uploads:
        existing = db.query(AnalysisRow).filter_by(upload_id=upload_id).first()
        if existing:
            continue
        # match the upload back to the analyzer output via builder cache?
        # builder doesn't expose it; cheaper to skip caching here and let
        # next run hit the analyzer again. Optional: add a writer hook.

    # Save storyboard
    sb_row = StoryboardRow(
        id=storyboard.storyboard_id,
        project_id=project_id,
        template_id=template.template_id,
        json=storyboard.model_dump(mode="json"),
        created_at=datetime.utcnow(),
    )
    db.add(sb_row)
    project_row.template_id = template.template_id
    project_row.storyboard_id = storyboard.storyboard_id
    project_row.updated_at = datetime.utcnow()
    db.commit()

    return storyboard


@router.get("", response_model=Optional[Storyboard])
def get_current_storyboard(project_id: str, db: Session = Depends(get_db)) -> Optional[Storyboard]:
    project_row = db.get(ProjectRow, project_id)
    if not project_row or not project_row.storyboard_id:
        return None
    sb_row = db.get(StoryboardRow, project_row.storyboard_id)
    if not sb_row:
        return None
    return Storyboard(**sb_row.json)


class PatchBody(BaseModel):
    storyboard: Storyboard


@router.put("", response_model=Storyboard)
def replace_storyboard(project_id: str, body: PatchBody, db: Session = Depends(get_db)) -> Storyboard:
    """Save manual edits from the UI (re-ordered shots, new assignments)."""
    project_row = db.get(ProjectRow, project_id)
    if not project_row:
        raise HTTPException(404, "Project not found")

    sb = body.storyboard
    sb.storyboard_id = sb.storyboard_id or str(uuid.uuid4())
    sb.project_id = project_id

    sb_row = db.get(StoryboardRow, sb.storyboard_id)
    if sb_row:
        sb_row.json = sb.model_dump(mode="json")
    else:
        sb_row = StoryboardRow(
            id=sb.storyboard_id,
            project_id=project_id,
            template_id=sb.template_id,
            json=sb.model_dump(mode="json"),
            created_at=datetime.utcnow(),
        )
        db.add(sb_row)

    project_row.storyboard_id = sb.storyboard_id
    project_row.updated_at = datetime.utcnow()
    db.commit()
    return sb
