"""Template model — analogous to LTX-Video's YAML inference configs."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .shot import ShotSlot


class PacingMode(str, Enum):
    FREE = "free"            # ignore audio, use template-defined durations
    BEAT = "beat"            # snap shots to beats
    DOWNBEAT = "downbeat"    # snap to downbeats only
    BAR = "bar"              # one shot per musical bar


class AudioCue(BaseModel):
    """When and how to use an audio source within the reel.

    Supports the pro editor's specs like 'music from 4s-8s' or 'voiceover from 12s-20s'.
    """
    track_query: str = Field(
        ...,
        description="Either a path within audio_library/, a tag query like 'mood:cinematic tempo:slow', "
                    "an absolute path prefixed with 'file:', or a generation prompt prefixed with 'gen:' "
                    "(e.g. 'gen:soft piano underscore')"
    )
    kind: str = Field("music", description="music | voiceover | sfx")
    start_time_sec: float = Field(0.0, ge=0)
    end_time_sec: Optional[float] = Field(None, description="None = end of reel")
    volume_db: float = Field(0.0, description="Gain in dB. -6 = half volume.")
    fade_in_sec: float = Field(0.5, ge=0)
    fade_out_sec: float = Field(1.0, ge=0)


class TextOverlaySpec(BaseModel):
    overlay_id: str
    text_template: str = Field(
        ...,
        description="Jinja-style template with {{property.address}}, {{property.price}}, etc."
    )
    position: str = Field("bottom_left", description="top_left, top_right, bottom_left, bottom_right, center")
    font_family: str = "Inter"
    font_size_px: int = 48
    color_hex: str = "#FFFFFF"
    background_hex: Optional[str] = Field(None, description="Optional pill background, e.g. #00000080")
    duration_sec: Optional[float] = Field(None, description="If set, overlay only shows this long inside the shot")
    fade_in_sec: float = 0.3
    fade_out_sec: float = 0.5


class Template(BaseModel):
    """Parameterized reel template authored by a pro editor.

    Mirrors LTX-Video YAML configs which encode per-timestep guidance/STG schedules
    and skip block lists. We encode per-shot motion, transitions, audio cues, and text overlays.
    """
    template_id: str
    name: str
    description: str
    author: str = "AutoHDR"
    version: str = "1.0.0"

    target_duration_sec: float = Field(60.0, gt=0)
    aspect_ratio: str = Field("9:16", description="9:16 (reel), 1:1 (grid), 16:9 (web)")
    pacing_mode: PacingMode = PacingMode.FREE

    shot_slots: list[ShotSlot]
    audio_cues: list[AudioCue] = Field(default_factory=list)
    text_overlays: list[TextOverlaySpec] = Field(default_factory=list)

    global_color_grade: Optional[str] = Field(None, description="Default LUT applied unless shot overrides")

    # Two-pass render config (parallels LTX-Video first_pass / second_pass)
    draft_resolution_p: int = Field(540, description="Vertical resolution for draft preview")
    final_resolution_p: int = Field(1080, description="Vertical resolution for final render")
    draft_crf: int = Field(28, description="x264 CRF for draft (higher = lower quality, faster)")
    final_crf: int = Field(20, description="x264 CRF for final")

    @property
    def slot_by_id(self) -> dict[str, ShotSlot]:
        return {s.slot_id: s for s in self.shot_slots}

    @property
    def text_overlay_by_id(self) -> dict[str, TextOverlaySpec]:
        return {o.overlay_id: o for o in self.text_overlays}
