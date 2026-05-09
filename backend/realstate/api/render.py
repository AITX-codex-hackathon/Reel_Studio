"""Render endpoints — kick off draft/final renders and stream progress."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..models.project import RenderJob, RenderStatus
from ..models.storyboard import Storyboard
from ..pipelines.multiscale_pipeline import MultiPassRenderer
from ..storage import ProjectRow, RenderRow, StoryboardRow, get_db
from ..storage.filesystem import ProjectFiles, TemplateLoader
from .ws import broadcast_render_progress

log = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/renders", tags=["renders"])

_loader = TemplateLoader()
_renderer = MultiPassRenderer()


@router.post("", response_model=RenderJob)
async def start_render(
    project_id: str,
    background_tasks: BackgroundTasks,
    pass_type: str = Query("draft", pattern="^(draft|final)$"),
    db: Session = Depends(get_db),
) -> RenderJob:
    project = db.get(ProjectRow, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.storyboard_id:
        raise HTTPException(400, "No storyboard yet. Generate one first.")

    sb_row = db.get(StoryboardRow, project.storyboard_id)
    if not sb_row:
        raise HTTPException(404, "Storyboard not found")
    storyboard = Storyboard(**sb_row.json)

    template = _loader.get(storyboard.template_id)
    if not template:
        raise HTTPException(404, f"Template {storyboard.template_id} not found")

    pf = ProjectFiles()
    out_path = pf.renders_dir(project_id) / f"{pass_type}.mp4"
    scratch = pf.scratch_dir(project_id)

    job = RenderRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        storyboard_id=storyboard.storyboard_id,
        pass_type=pass_type,
        status=RenderStatus.PENDING.value,
        progress=0.0,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id
    background_tasks.add_task(
        _run_render,
        job_id=job_id,
        project_id=project_id,
        pass_type=pass_type,
        storyboard=storyboard,
        template_id=storyboard.template_id,
        out_path=out_path,
        scratch=scratch,
    )

    return RenderJob.model_validate(job)


@router.get("/{render_id}", response_model=RenderJob)
def get_render(project_id: str, render_id: str, db: Session = Depends(get_db)) -> RenderJob:
    row = db.query(RenderRow).filter_by(project_id=project_id, id=render_id).first()
    if not row:
        raise HTTPException(404, "Render not found")
    return RenderJob.model_validate(row)


@router.get("", response_model=list[RenderJob])
def list_renders(project_id: str, db: Session = Depends(get_db)) -> list[RenderJob]:
    rows = (
        db.query(RenderRow)
        .filter_by(project_id=project_id)
        .order_by(RenderRow.created_at.desc())
        .all()
    )
    return [RenderJob.model_validate(r) for r in rows]


@router.get("/{render_id}/file")
def download_render(project_id: str, render_id: str, db: Session = Depends(get_db)) -> FileResponse:
    row = db.query(RenderRow).filter_by(project_id=project_id, id=render_id).first()
    if not row or not row.output_path or not Path(row.output_path).exists():
        raise HTTPException(404, "Render file not found")
    return FileResponse(
        path=row.output_path,
        media_type="video/mp4",
        filename=f"{project_id}_{row.pass_type}.mp4",
    )


async def _run_render(
    job_id: str,
    project_id: str,
    pass_type: str,
    storyboard: Storyboard,
    template_id: str,
    out_path: Path,
    scratch: Path,
) -> None:
    """Background render task. Updates DB row + pushes WS progress."""
    from ..storage import SessionLocal

    template = _loader.get(template_id)
    if not template:
        log.error("Template %s vanished mid-render", template_id)
        return

    assert SessionLocal is not None
    with SessionLocal() as db:
        row = db.get(RenderRow, job_id)
        if not row:
            return
        row.status = RenderStatus.RUNNING.value
        db.commit()

    try:
        gen = (
            _renderer.draft(storyboard, template, out_path, scratch_dir=scratch)
            if pass_type == "draft"
            else _renderer.final(storyboard, template, out_path, scratch_dir=scratch)
        )

        last_push = 0.0
        async for progress in gen:
            # Throttle DB + WS updates to ~5 Hz
            now = asyncio.get_event_loop().time()
            if now - last_push >= 0.2 or progress.progress >= 1.0:
                last_push = now
                with SessionLocal() as db:
                    row = db.get(RenderRow, job_id)
                    if row:
                        row.progress = progress.progress
                        db.commit()
                await broadcast_render_progress(
                    project_id=project_id,
                    payload={
                        "render_id": job_id,
                        "pass_type": pass_type,
                        "progress": progress.progress,
                        "seconds_done": progress.seconds_done,
                        "fps": progress.fps,
                    },
                )

        with SessionLocal() as db:
            row = db.get(RenderRow, job_id)
            if row:
                row.status = RenderStatus.SUCCEEDED.value
                row.progress = 1.0
                row.output_path = str(out_path)
                row.duration_sec = storyboard.total_duration_sec
                row.finished_at = datetime.utcnow()
                db.commit()

        await broadcast_render_progress(
            project_id=project_id,
            payload={
                "render_id": job_id,
                "pass_type": pass_type,
                "progress": 1.0,
                "status": "succeeded",
                "output_url": f"/projects/{project_id}/renders/{job_id}/file",
            },
        )

    except Exception as e:
        log.exception("Render %s failed", job_id)
        with SessionLocal() as db:
            row = db.get(RenderRow, job_id)
            if row:
                row.status = RenderStatus.FAILED.value
                row.error = str(e)[:2000]
                row.finished_at = datetime.utcnow()
                db.commit()
        await broadcast_render_progress(
            project_id=project_id,
            payload={
                "render_id": job_id,
                "pass_type": pass_type,
                "status": "failed",
                "error": str(e)[:500],
            },
        )
