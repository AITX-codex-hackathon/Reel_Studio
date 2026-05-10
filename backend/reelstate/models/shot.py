"""Shot model — analogous to LTX-Video's ConditioningItem."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

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
    """A resolved shot — slot + assigned image + final timing."""
    slot_id: str
    image_path: str = Field(..., description="Absolute path to the still (uploaded or generated)")
    start_time_sec: float = Field(..., ge=0)
    duration_sec: float = Field(..., gt=0)
    motion: MotionPreset
    motion_strength: float = Field(0.5, ge=0.0, le=1.0)
    transition_in: TransitionType
    color_grade: Optional[str] = None
    text_overlay_id: Optional[str] = None
    is_generated: bool = Field(False, description="True if image came from FAL")
    source_upload_id: Optional[str] = None

    # Style recipe fields — set during storyboard build
    room_type: Optional[str] = None
    style_recipe_id: Optional[str] = None
    style_notes: Optional[str] = Field(
        None,
        description="Editor-agent direction for camera, mood, transitions, and story intent.",
    )
    scene_purpose: Optional[str] = Field(
        None,
        description="Narrative purpose of this scene inside the reel's binding concept.",
    )
    beat_plan: Optional[str] = Field(
        None,
        description="Beat-level timing and cut intention for this shot.",
    )
    masking_plan: Optional[str] = Field(
        None,
        description="Source-safe mask and holdout plan for image-to-video generation.",
    )
    transition_plan: Optional[str] = Field(
        None,
        description="Motivated transition logic into or out of this shot.",
    )
    ingress_seam: Optional[str] = Field(
        None,
        description="How this shot receives camera velocity, light, and composition from the previous shot.",
    )
    egress_seam: Optional[str] = Field(
        None,
        description="How this shot exits into the next shot without a temporal or camera-vector jerk.",
    )
    shared_anchors_to_next: list[str] = Field(
        default_factory=list,
        description="Visible anchors shared with the next shot, such as flooring, ceiling height, glass, view, light direction, or material texture.",
    )
    bridge_instructions: Optional[str] = Field(
        None,
        description="Outgoing first/last-frame bridge instructions from this shot into the next shot.",
    )
    bridge_strategy: Optional[str] = Field(
        None,
        description="Outgoing editor intent: handshake, reveal, whip_pan, simple_cut, match_cut, or legacy technical strategy.",
    )
    transition_logic: Optional[dict[str, Any]] = Field(
        None,
        description="Agent's outgoing edit decision: strategy, justification, spatial continuity, technical execution, and risk notes.",
    )
    ramp_profile: Optional[str] = Field(
        None,
        description="Agent-controlled clip velocity profile: cruise, reveal, or impact.",
    )
    visual_distance_score: Optional[float] = Field(
        None,
        ge=1.0,
        le=10.0,
        description="Agent-estimated visual distance from this shot to the next shot. 1=same space, 10=very different.",
    )
    bridge_duration_sec: Optional[float] = Field(
        None,
        gt=0.0,
        description="Preferred outgoing bridge duration after post-processing.",
    )
    velocity_vector: Optional[str] = Field(
        None,
        description="Camera inertia vector to inherit at the start of this scene, e.g. forward_dolly_25pct, lateral_pan_left_20pct.",
    )
    movement_intensity: Optional[str] = Field(
        None,
        description="Outgoing movement intensity for DI and sound design: calm, moderate, or fast.",
    )
    continuity_notes: Optional[str] = Field(
        None,
        description="Scene continuity notes for light, geometry, camera direction, and visual grammar.",
    )
    rubric_plan: Optional[dict[str, Any]] = Field(
        None,
        description="Rubric.json scene plan: narrative, audio sync, optics, kinetic path, masking, transitions, and FAL prompt.",
    )
    style_recipe_prompt: Optional[str] = Field(
        None,
        description="Hidden grounded cinematic prompt generated by the agent for the video provider.",
    )
    user_direction: Optional[str] = Field(
        None,
        description="Optional user-facing direction merged into the hidden render prompt for this shot.",
    )
    is_transition_bridge: bool = Field(
        False,
        description="True when this is an inserted first/last-frame transition clip rather than a primary scene.",
    )
    trim_handle_sec: float = Field(
        0.0,
        ge=0.0,
        description="Generated pre-roll handle to discard before final concat.",
    )

    # Set during render — path to FAL-generated .mp4 clip
    video_clip_path: Optional[str] = None

    @property
    def end_time_sec(self) -> float:
        return self.start_time_sec + self.duration_sec
