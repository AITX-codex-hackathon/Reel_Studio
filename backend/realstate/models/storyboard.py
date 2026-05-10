"""Storyboard — resolved shots ready to render."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .shot import Shot
from .template import AudioCue, TextOverlaySpec


class ResolvedShot(Shot):
    """Shot with rendered text content baked in."""
    rendered_text_overlay: Optional[str] = None


class StoryboardMusic(BaseModel):
    source: str
    track_id: str
    title: str
    artist: str
    audio_path: str
    timestamps_path: str
    manifest_path: str
    cuts_dir: Optional[str] = None
    tempo: Optional[float] = None
    beat_count: int = 0
    beat_timestamps_ms: list[int] = Field(default_factory=list)
    attribution: str


class Storyboard(BaseModel):
    storyboard_id: str
    project_id: str
    template_id: str = "auto"

    shots: list[ResolvedShot]
    audio_cues: list[AudioCue]
    text_overlays: list[TextOverlaySpec]
    music: Optional[StoryboardMusic] = None

    total_duration_sec: float = Field(..., gt=0)
    aspect_ratio: str

    # Beat timestamps from beat-analysis module (populated externally when ready)
    beat_timestamps: list[float] = Field(default_factory=list)

    # Pixabay or local music track
    music_url: Optional[str] = None

    generated_slot_ids: list[str] = Field(default_factory=list)
    unfilled_slot_ids: list[str] = Field(default_factory=list)
    notes: str = ""

    @property
    def shot_count(self) -> int:
        return len(self.shots)
