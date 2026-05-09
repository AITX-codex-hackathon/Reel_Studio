"""Color grading via FFmpeg curves / colorbalance / eq filters.

For a v1 we ship preset 'looks' implemented as filter chains rather than .cube LUTs.
A LUT loader (haldclut) can be added later.
"""
from __future__ import annotations

from typing import Optional

# Each preset is a filter chain string applied to a video stream
LUT_PRESETS: dict[str, str] = {
    "warm_cinematic": (
        # warm shadows, slight teal highlights, lifted blacks, gentle contrast
        "eq=contrast=1.08:saturation=1.05:gamma=0.98,"
        "colorbalance=rs=0.05:bs=-0.05:gs=0.02:rh=-0.04:bh=0.04"
    ),
    "cool_modern": (
        # cooler whites, crisp contrast, slight desaturation
        "eq=contrast=1.12:saturation=0.92:gamma=0.96,"
        "colorbalance=rs=-0.04:bs=0.06:rh=0.02:bh=0.02"
    ),
    "warm_lifestyle": (
        # warmer overall, lifted shadows, golden cast
        "eq=contrast=1.04:saturation=1.10:gamma=1.02,"
        "colorbalance=rs=0.08:bs=-0.06:rm=0.03:bm=-0.03"
    ),
    "punchy_vivid": (
        "eq=contrast=1.18:saturation=1.20:gamma=0.95"
    ),
    "muted_film": (
        "eq=contrast=1.05:saturation=0.85:gamma=1.00,"
        "curves=preset=vintage"
    ),
}

AVAILABLE_LUTS = list(LUT_PRESETS.keys())


def color_grade_filter(grade: Optional[str]) -> Optional[str]:
    """Return the filter chain for a named grade, or None if no grade applies."""
    if not grade:
        return None
    return LUT_PRESETS.get(grade)
