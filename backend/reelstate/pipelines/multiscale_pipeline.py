"""MultiPassRenderer — two-pass render (draft → final).

Analogous to LTX-Video's `LTXMultiScalePipeline`: a low-res first pass for fast
preview, then a high-res second pass for the deliverable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from ..models.render_config import AspectRatio, RenderConfig, RenderPass
from ..models.storyboard import Storyboard
from ..models.template import Template
from ..render.encoder import RenderProgress
from .reel_pipeline import ReelPipeline

log = logging.getLogger(__name__)


@dataclass
class MultiPassResult:
    draft_path: Optional[Path] = None
    final_path: Optional[Path] = None


class MultiPassRenderer:
    def __init__(self, pipeline: Optional[ReelPipeline] = None):
        self.pipeline = pipeline or ReelPipeline()

    async def draft(
        self,
        storyboard: Storyboard,
        template: Optional[Template],
        output_path: Path,
        scratch_dir: Optional[Path] = None,
    ) -> AsyncIterator[RenderProgress]:
        config = self._config_for_pass(
            storyboard=storyboard,
            template=template,
            pass_type=RenderPass.DRAFT,
        )
        async for p in self.pipeline.render(
            storyboard=storyboard,
            config=config,
            output_path=output_path,
            global_color_grade=template.global_color_grade if template else None,
            scratch_dir=scratch_dir,
        ):
            yield p

    async def final(
        self,
        storyboard: Storyboard,
        template: Optional[Template],
        output_path: Path,
        scratch_dir: Optional[Path] = None,
    ) -> AsyncIterator[RenderProgress]:
        config = self._config_for_pass(
            storyboard=storyboard,
            template=template,
            pass_type=RenderPass.FINAL,
        )
        async for p in self.pipeline.render(
            storyboard=storyboard,
            config=config,
            output_path=output_path,
            global_color_grade=template.global_color_grade if template else None,
            scratch_dir=scratch_dir,
        ):
            yield p

    def _config_for_pass(
        self,
        storyboard: Storyboard,
        template: Optional[Template],
        pass_type: RenderPass,
    ) -> RenderConfig:
        # Pick aspect ratio from storyboard (same in both passes)
        ar_str = storyboard.aspect_ratio
        ar = {"9:16": AspectRatio.REEL_9_16, "1:1": AspectRatio.SQUARE_1_1, "16:9": AspectRatio.WIDE_16_9}.get(ar_str, AspectRatio.REEL_9_16)

        if pass_type == RenderPass.DRAFT:
            v_res = template.draft_resolution_p if template else 540
            crf = template.draft_crf if template else 28
            preset = "ultrafast"
            watermark = True
        else:
            v_res = template.final_resolution_p if template else 1080
            crf = template.final_crf if template else 22
            preset = "medium"
            watermark = False

        # Compute (w, h) by scaling baseline AR dims so that the *vertical* dim hits v_res
        baseline_w, baseline_h = ar.dimensions
        scale = v_res / baseline_h
        # Round to even numbers (libx264 needs even dims for yuv420p)
        w = int(round(baseline_w * scale / 2) * 2)
        h = int(round(baseline_h * scale / 2) * 2)

        return RenderConfig(
            project_id=storyboard.project_id,
            storyboard_id=storyboard.storyboard_id,
            pass_type=pass_type,
            aspect_ratio=ar,
            fps=30,
            width=w,
            height=h,
            crf=crf,
            preset=preset,
            audio_bitrate_kbps=192 if pass_type == RenderPass.FINAL else 128,
            seed=42,
            add_watermark=watermark,
        )
