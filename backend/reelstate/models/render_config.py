"""RenderConfig — analogous to LTX-Video's InferenceConfig dataclass."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AspectRatio(str, Enum):
    REEL_9_16 = "9:16"
    SQUARE_1_1 = "1:1"
    WIDE_16_9 = "16:9"

    @property
    def dimensions(self) -> tuple[int, int]:
        # vertical dimension is implicit; we return (w, h) at 1080p baseline
        return {
            AspectRatio.REEL_9_16: (1080, 1920),
            AspectRatio.SQUARE_1_1: (1080, 1080),
            AspectRatio.WIDE_16_9: (1920, 1080),
        }[self]


class RenderPass(str, Enum):
    DRAFT = "draft"
    FINAL = "final"


class RenderConfig(BaseModel):
    """All knobs the renderer takes for one pass.

    Mirrors LTX-Video's InferenceConfig: dimensions, seed, quality params,
    encoding settings — but for FFmpeg-based pixel-space rendering rather
    than diffusion.
    """
    project_id: str
    storyboard_id: str
    pass_type: RenderPass = RenderPass.DRAFT

    aspect_ratio: AspectRatio = AspectRatio.REEL_9_16
    fps: int = Field(30, ge=24, le=60)
    width: int = Field(1080, gt=0)
    height: int = Field(1920, gt=0)
    crf: int = Field(20, ge=0, le=51, description="x264 CRF — lower = higher quality")
    preset: str = Field("medium", description="x264 preset: ultrafast..veryslow")
    audio_bitrate_kbps: int = Field(192, gt=0)

    seed: int = Field(42, description="Used for any randomized choices (e.g. transition pick)")

    add_watermark: bool = Field(False, description="Stamp 'PREVIEW' on draft renders")
    output_filename: Optional[str] = None

    def output_resolution(self) -> tuple[int, int]:
        return (self.width, self.height)
