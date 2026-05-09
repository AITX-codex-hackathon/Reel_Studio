"""Free To Use music browsing and project music insertion."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..integrations.free_music import FreeMusicClient, FreeMusicError, load_timestamps
from ..storage import ProjectMusicRow, ProjectRow, get_db, get_sessionmaker
from ..storage.filesystem import ProjectFiles

router = APIRouter(tags=["free-music"])

_client = FreeMusicClient()
_files = ProjectFiles()
_jobs_lock = threading.Lock()
_music_jobs: dict[str, dict[str, Any]] = {}


class FreeMusicTrackOut(BaseModel):
    id: str
    title: str
    artist: str
    duration_sec: Optional[float] = None
    genre: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None


class MusicInsertBody(BaseModel):
    track_id: str
    make_cuts: bool = True
    include_tail: bool = False


class MusicInsertJobOut(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str = ""
    result: Optional["ProjectMusicOut"] = None
    error: Optional[str] = None


class ProjectMusicOut(BaseModel):
    id: str
    project_id: str
    source: str
    track_id: str
    title: str
    artist: str
    duration_sec: Optional[float] = None
    audio_path: str
    metadata_path: str
    timestamps_path: str
    cuts_dir: Optional[str] = None
    manifest_path: str
    tempo: Optional[float] = None
    beat_count: int
    beat_timestamps_ms: list[int] = Field(default_factory=list)
    attribution: str
    created_at: datetime


MusicInsertJobOut.model_rebuild()


@router.get("/free-music/tracks", response_model=list[FreeMusicTrackOut])
def list_free_music_tracks(
    query: Optional[str] = Query(None, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    order: str = "release_date",
    sort: str = Query("desc", pattern="^(asc|desc)$"),
) -> list[FreeMusicTrackOut]:
    try:
        tracks = _client.list_tracks(
            query=query,
            limit=limit,
            offset=offset,
            order=order,
            sort=sort,
        )
    except FreeMusicError as error:
        raise HTTPException(502, str(error)) from error

    return [
        FreeMusicTrackOut(
            id=track.id,
            title=track.title,
            artist=track.artist,
            duration_sec=track.duration_sec,
            genre=track.genre,
            tags=track.tags,
            thumbnail_url=track.thumbnail_url,
            preview_url=track.preview_url,
        )
        for track in tracks
    ]


@router.get("/projects/{project_id}/music/current", response_model=Optional[ProjectMusicOut])
def get_current_music(project_id: str, db: Session = Depends(get_db)) -> Optional[ProjectMusicOut]:
    row = _latest_music_row(project_id, db)
    if not row:
        return None
    return _music_row_to_out(row)


@router.post("/projects/{project_id}/music/insert", response_model=MusicInsertJobOut)
def insert_project_music(
    project_id: str,
    body: MusicInsertBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MusicInsertJobOut:
    project = db.get(ProjectRow, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    job_id = f"music_{uuid.uuid4().hex}"
    job = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.05,
        "message": "Preparing music",
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _music_jobs[job_id] = job

    background_tasks.add_task(
        _prepare_project_music_job,
        job_id,
        project_id,
        body.track_id,
        body.make_cuts,
        body.include_tail,
    )
    return MusicInsertJobOut(**job)


@router.get("/projects/{project_id}/music/jobs/{job_id}", response_model=MusicInsertJobOut)
def get_music_insert_job(project_id: str, job_id: str) -> MusicInsertJobOut:
    with _jobs_lock:
        job = _music_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Music job not found")
    result = job.get("result")
    if result and result.project_id != project_id:
        raise HTTPException(404, "Music job not found")
    return MusicInsertJobOut(**job)


@router.get("/projects/{project_id}/music/file")
def get_project_music_file(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    row = _latest_music_row(project_id, db)
    if not row or not Path(row.audio_path).exists():
        raise HTTPException(404, "Project music not found")
    return FileResponse(
        path=row.audio_path,
        media_type="audio/mpeg",
        filename=f"{row.artist} - {row.title}.mp3",
    )


def _prepare_project_music_job(
    job_id: str,
    project_id: str,
    track_id: str,
    make_cuts: bool,
    include_tail: bool,
) -> None:
    _set_job(job_id, status="running", progress=0.15, message="Downloading track")
    try:
        project_track_dir = _files.music_dir(project_id) / "free-to-use" / track_id
        prepared = _client.prepare_track(
            track_id=track_id,
            output_dir=project_track_dir,
            make_cuts=make_cuts,
            include_tail=include_tail,
        )

        _set_job(job_id, progress=0.85, message="Saving beat grid")
        SessionMaker = get_sessionmaker()
        with SessionMaker() as db:
            row = ProjectMusicRow(
                id=str(uuid.uuid4()),
                project_id=project_id,
                source=prepared.source,
                track_id=prepared.track_id,
                title=prepared.title,
                artist=prepared.artist,
                duration_sec=prepared.duration_sec,
                audio_path=str(prepared.audio_path),
                metadata_path=str(prepared.metadata_path),
                timestamps_path=str(prepared.timestamps_path),
                cuts_dir=str(prepared.cuts_dir) if prepared.cuts_dir else None,
                manifest_path=str(prepared.manifest_path),
                tempo=prepared.tempo,
                beat_count=prepared.beat_count,
                attribution=prepared.attribution,
                raw=prepared.manifest(),
                created_at=datetime.utcnow(),
            )
            db.add(row)
            project = db.get(ProjectRow, project_id)
            if project:
                project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(row)
            result = _music_row_to_out(row)

        _set_job(
            job_id,
            status="complete",
            progress=1.0,
            message="Music inserted",
            result=result,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            progress=1.0,
            message="Music insert failed",
            error=str(error),
        )


def _set_job(job_id: str, **updates: Any) -> None:
    with _jobs_lock:
        job = _music_jobs.get(job_id)
        if not job:
            return
        job.update(updates)


def _latest_music_row(project_id: str, db: Session) -> Optional[ProjectMusicRow]:
    return (
        db.query(ProjectMusicRow)
        .filter_by(project_id=project_id)
        .order_by(ProjectMusicRow.created_at.desc())
        .first()
    )


def _music_row_to_out(row: ProjectMusicRow) -> ProjectMusicOut:
    beat_timestamps: list[int] = []
    timestamps_path = Path(row.timestamps_path)
    if timestamps_path.exists():
        try:
            beat_timestamps = load_timestamps(timestamps_path)
        except FreeMusicError:
            beat_timestamps = []

    return ProjectMusicOut(
        id=row.id,
        project_id=row.project_id,
        source=row.source,
        track_id=row.track_id,
        title=row.title,
        artist=row.artist,
        duration_sec=row.duration_sec,
        audio_path=row.audio_path,
        metadata_path=row.metadata_path,
        timestamps_path=row.timestamps_path,
        cuts_dir=row.cuts_dir,
        manifest_path=row.manifest_path,
        tempo=row.tempo,
        beat_count=row.beat_count,
        beat_timestamps_ms=beat_timestamps,
        attribution=row.attribution,
        created_at=row.created_at,
    )
