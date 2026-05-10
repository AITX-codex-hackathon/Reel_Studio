"""Post-production helpers for AI-generated bridge clips.

These filters intentionally stay modest. The goal is to hide small model
imperfections without turning calm luxury footage into over-processed video.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class BridgePostProcessResult:
    output_path: Path
    applied_motion_smoothing: bool
    color_filter: str


async def cook_transition_bridge(
    *,
    input_path: Path,
    output_path: Path,
    start_image_path: Path,
    end_image_path: Path,
    duration_sec: float,
    raw_duration_sec: float,
    movement_intensity: str,
    out_w: int,
    out_h: int,
    fps: int,
    ffmpeg_bin: str = "ffmpeg",
) -> Optional[BridgePostProcessResult]:
    """Trim and normalize a raw first/last-frame bridge clip before concat."""
    if not input_path.exists():
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    color_filter = _color_balance_filter(start_image_path, end_image_path)
    raw_duration_sec = max(duration_sec, raw_duration_sec, 0.5)
    time_scale = max(0.05, duration_sec / raw_duration_sec)
    filters = [
        f"trim=0:{raw_duration_sec:.3f}",
        f"setpts=(PTS-STARTPTS)*{time_scale:.6f}",
    ]
    ramp_filter = _s_curve_setpts_filter(duration_sec, ramp_sec=min(0.5, duration_sec / 3))
    if ramp_filter:
        filters.append(ramp_filter)
    filters.extend([
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase",
        f"crop={out_w}:{out_h}",
    ])
    if color_filter:
        filters.append(color_filter)

    apply_motion_smoothing = _should_apply_motion_smoothing(movement_intensity)
    if apply_motion_smoothing:
        filters.append("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")

    filters.extend([f"fps={fps}", "format=yuv420p"])
    cmd = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vf",
        ",".join(filters),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        os.getenv("FFMPEG_POST_PRESET", "veryfast"),
        "-crf",
        os.getenv("FFMPEG_POST_CRF", "19"),
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning("Bridge post-process failed for %s: %s", input_path, stderr.decode(errors="ignore")[-1200:])
        return None
    return BridgePostProcessResult(
        output_path=output_path,
        applied_motion_smoothing=apply_motion_smoothing,
        color_filter=color_filter,
    )


def _should_apply_motion_smoothing(movement_intensity: str) -> bool:
    enabled = os.getenv("FFMPEG_BRIDGE_MOTION_SMOOTHING", "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return False
    return movement_intensity == "fast"


def _s_curve_setpts_filter(duration_sec: float, ramp_sec: float) -> str:
    if ramp_sec <= 0 or duration_sec <= ramp_sec * 2:
        return ""
    end_start = duration_sec - ramp_sec
    expr = (
        f"if(lt(T,{ramp_sec:.6f}),"
        f"(pow(T/{ramp_sec:.6f},3)*{ramp_sec:.6f})/TB,"
        f"if(gt(T,{end_start:.6f}),"
        f"({end_start:.6f}+(1-pow(1-((T-{end_start:.6f})/{ramp_sec:.6f}),3))*{ramp_sec:.6f})/TB,"
        "T/TB))"
    )
    return f"setpts='{expr}'"


def _color_balance_filter(start_image_path: Path, end_image_path: Path) -> str:
    start = _image_rgb_stats(start_image_path)
    end = _image_rgb_stats(end_image_path)
    if not start or not end:
        return ""

    target = tuple((start[i] + end[i]) / 2 for i in range(3))
    r, g, b = target
    avg = max(1.0, (r + g + b) / 3)
    luma = max(-0.06, min(0.06, (avg - 128.0) / 255.0 * 0.35))
    red_shift = max(-0.05, min(0.05, (r - avg) / 255.0 * 0.28))
    green_shift = max(-0.05, min(0.05, (g - avg) / 255.0 * 0.28))
    blue_shift = max(-0.05, min(0.05, (b - avg) / 255.0 * 0.28))

    # Apply only a gentle correction; the source/end frames still do the real anchoring.
    return (
        f"eq=brightness={luma:.4f}:contrast=1.025:saturation=1.035,"
        f"colorbalance=rs={red_shift:.4f}:gs={green_shift:.4f}:bs={blue_shift:.4f}:"
        f"rm={red_shift / 2:.4f}:gm={green_shift / 2:.4f}:bm={blue_shift / 2:.4f}"
    )


def _image_rgb_stats(image_path: Path) -> Optional[tuple[float, float, float]]:
    try:
        from PIL import Image, ImageStat  # type: ignore

        with Image.open(image_path) as image:
            rgb = image.convert("RGB").resize((64, 64))
            stat = ImageStat.Stat(rgb)
            r, g, b = stat.mean[:3]
            return float(r), float(g), float(b)
    except Exception:
        return None
