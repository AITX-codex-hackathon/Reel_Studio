"""Project, Upload, ImageAnalysis, RenderJob — domain entities."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: Optional[str] = None
    price: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    description: Optional[str] = None
    template_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class Upload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    filename: str
    path: str
    width: int
    height: int
    sha256: str
    created_at: datetime


class ImageAnalysis(BaseModel):
    """Cached vision-model output for one upload.

    Pre-computed so re-rendering / template-switching doesn't re-bill the API.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    upload_id: str
    room_type: str  # exterior, kitchen, bedroom, etc.
    quality_score: float = Field(..., ge=0.0, le=1.0)
    framing: str  # wide, medium, close, detail
    lighting: str  # bright, soft, golden_hour, low_light, harsh
    dominant_colors: list[str]
    suggested_motion: str  # one of MotionPreset values
    notes: str
    raw: dict[str, Any] = Field(default_factory=dict, description="Full agent response for debugging")
    created_at: datetime


class RenderStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    storyboard_id: str
    pass_type: str  # 'draft' | 'final'
    status: RenderStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    output_path: Optional[str] = None
    duration_sec: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
