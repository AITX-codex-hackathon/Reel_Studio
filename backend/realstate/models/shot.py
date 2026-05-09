"""Shot model — analogous to LTX-Video's ConditioningItem."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MotionPreset(str, Enum):
    SLOW_ZOOM_IN = "slow_zoom_in"
    SLOW_ZOOM_OUT = "slow_zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    STATIC = "static"
    GENERATIVE = "generative"  # offload to Runway/Luma


class TransitionType(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    WHIP_PAN = "whip_pan"
    FADE = "fade"


class ShotSlot(BaseModel):
    """A slot in a template — describes what kind of image should fill it.

    Mirrors the LTX-Video pattern of conditioning specs (frame_number, strength)
    but for the editing domain (room type, mood, framing).
    """
    slot_id: str
    description: str = Field(..., description="Pro editor's natural-language brief for this slot")
    room_type: Optional[str] = Field(
        None,
        description="exterior, foyer, kitchen, living_room, bedroom, bathroom, backyard, view, detail, lifestyle"
    )
    duration_sec: float = Field(..., gt=0)
    motion: MotionPreset = MotionPreset.STATIC
    motion_strength: float = Field(0.5, ge=0.0, le=1.0)
    transition_in: TransitionType = TransitionType.CUT
    color_grade: Optional[str] = Field(None, description="LUT name (e.g. 'warm_cinematic', 'cool_modern')")
    text_overlay_id: Optional[str] = Field(None, description="Reference to a text overlay defined in the template")
    must_fill: bool = Field(True, description="If False and no upload matches, the slot is dropped (not generated)")
    fallback_to_generated: bool = Field(
        True, description="If no upload matches and must_fill, generate via fal.ai"
    )
    generation_prompt: Optional[str] = Field(
        None, description="Prompt used by fal.ai when fallback fires"
    )


class Shot(BaseModel):
    """A resolved shot — slot + assigned image + final timing.

    Direct analog of LTX-Video's `ConditioningItem(media, frame_number, strength)`.
    Here the "media" is an image path and "frame_number" becomes "start_time".
    """
    slot_id: str
    image_path: str = Field(..., description="Absolute path to the still (uploaded or generated)")
    start_time_sec: float = Field(..., ge=0)
    duration_sec: float = Field(..., gt=0)
    motion: MotionPreset
    motion_strength: float = Field(0.5, ge=0.0, le=1.0)
    transition_in: TransitionType
    color_grade: Optional[str] = None
    text_overlay_id: Optional[str] = None
    is_generated: bool = Field(False, description="True if image came from fal.ai")
    source_upload_id: Optional[str] = None

    @property
    def end_time_sec(self) -> float:
        return self.start_time_sec + self.duration_sec
