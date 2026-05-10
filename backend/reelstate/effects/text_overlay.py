"""Text overlay rendering.

We pre-render each overlay as a transparent PNG using PIL/Pillow, then have
FFmpeg composite it onto the shot via the `overlay` filter. This avoids
depending on FFmpeg being built with libfreetype (Homebrew's default ffmpeg
omits drawtext), and produces higher-quality antialiased text.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..models.template import TextOverlaySpec

log = logging.getLogger(__name__)

_DEFAULT_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    # Linux (common locations)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def _resolve_font(font_path: Optional[str], font_size_px: int) -> ImageFont.ImageFont:
    candidates: list[str] = []
    if font_path:
        candidates.append(font_path)
    candidates.extend(_DEFAULT_FONT_CANDIDATES)
    for c in candidates:
        try:
            return ImageFont.truetype(c, size=font_size_px)
        except (OSError, IOError):
            continue
    log.warning("No TrueType font found — falling back to PIL default (poor quality)")
    return ImageFont.load_default()


def _hex_to_rgba(hex_str: str, default_alpha: int = 255) -> tuple[int, int, int, int]:
    s = hex_str.lstrip("#")
    if len(s) == 6:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), default_alpha
    if len(s) == 8:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
    return 255, 255, 255, default_alpha


def render_overlay_png(
    spec: TextOverlaySpec,
    rendered_text: str,
    canvas_w: int,
    canvas_h: int,
    out_path: Path,
    font_path: Optional[str] = None,
) -> Path:
    """Render the text+pill overlay onto a transparent canvas of (canvas_w, canvas_h).

    Returns the path the PNG was written to.
    """
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _resolve_font(font_path, spec.font_size_px)

    # Multi-line text support — split on \n
    lines = rendered_text.split("\n")
    line_sizes = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

    max_w = max(w for w, _ in line_sizes) if line_sizes else 0
    line_h = max(h for _, h in line_sizes) if line_sizes else 0
    line_gap = int(line_h * 0.25)
    text_w = max_w
    text_h = (line_h + line_gap) * len(lines) - line_gap if lines else 0

    pad = max(20, spec.font_size_px // 3)
    box_w = text_w + pad * 2
    box_h = text_h + pad * 2

    # Position
    margin = 64
    if spec.position == "top_left":
        bx, by = margin, margin
    elif spec.position == "top_right":
        bx, by = canvas_w - box_w - margin, margin
    elif spec.position == "bottom_left":
        bx, by = margin, canvas_h - box_h - margin * 2
    elif spec.position == "bottom_right":
        bx, by = canvas_w - box_w - margin, canvas_h - box_h - margin * 2
    else:  # center
        bx = (canvas_w - box_w) // 2
        by = (canvas_h - box_h) // 2

    # Background pill
    if spec.background_hex:
        bg_rgba = _hex_to_rgba(spec.background_hex, default_alpha=180)
        radius = max(12, pad // 2)
        try:
            draw.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=radius, fill=bg_rgba)
        except AttributeError:
            draw.rectangle((bx, by, bx + box_w, by + box_h), fill=bg_rgba)

    # Text
    text_color = _hex_to_rgba(spec.color_hex)
    cy = by + pad
    for line, (lw, _) in zip(lines, line_sizes):
        cx = bx + (box_w - lw) // 2
        draw.text((cx, cy), line, font=font, fill=text_color)
        cy += line_h + line_gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def overlay_filter_chain(
    overlay_input_label: str,
    overlay_duration_sec: float,
    fade_in_sec: float,
    fade_out_sec: float,
) -> str:
    """Build the filter chain for the overlay PNG stream.

    The PNG is loaded as a looped image input. We:
      - normalize to yuva420p so alpha is preserved
      - set its PTS to start at 0
      - apply fade-in / fade-out on alpha
      - the calling site combines it with the shot stream via `overlay` filter
    """
    parts = [
        "format=yuva420p",
        "setpts=PTS-STARTPTS",
    ]
    if fade_in_sec > 0:
        parts.append(f"fade=t=in:st=0:d={fade_in_sec:.3f}:alpha=1")
    if fade_out_sec > 0:
        fade_out_start = max(0.0, overlay_duration_sec - fade_out_sec)
        parts.append(f"fade=t=out:st={fade_out_start:.3f}:d={fade_out_sec:.3f}:alpha=1")
    return ",".join(parts)
