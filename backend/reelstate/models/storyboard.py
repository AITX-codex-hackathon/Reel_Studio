"""Storyboard — resolved template + shots, ready to render.

Analogous to LTX-Video's patchifier output: takes a template (config) and the
user's image set, then produces an ordered, timed sequence ready for the renderer.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .shot import Shot
from .template import AudioCue, TextOverlaySpec


class ResolvedShot(Shot):
    """Same as Shot but with the rendered text content baked in (after Jinja eval)."""
    rendered_text_overlay: Optional[str] = None


class Storyboard(BaseModel):
    storyboard_id: str
    project_id: str
    template_id: str

    shots: list[ResolvedShot]
    audio_cues: list[AudioCue]
    text_overlays: list[TextOverlaySpec]

    total_duration_sec: float = Field(..., gt=0)
    aspect_ratio: str

    # Per-shot annotation: which slots fell back to generation
    generated_slot_ids: list[str] = Field(default_factory=list)
    # Per-shot annotation: which slots couldn't be filled at all
    unfilled_slot_ids: list[str] = Field(default_factory=list)

    notes: str = Field(
        "",
        description="Human-readable notes from the agent (which images went where, why fallbacks fired)",
    )

    @property
    def shot_count(self) -> int:
        return len(self.shots)
