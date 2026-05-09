"""Ken Burns motion — pan/zoom on a still.

We avoid FFmpeg's notoriously buggy `zoompan` filter by pre-scaling the image
to a generous canvas, then animating crop coordinates with `crop` + per-frame
expressions. This produces smooth, jitter-free motion at any aspect ratio.
"""
from __future__ import annotations

from ..models.shot import MotionPreset

# Render canvas — image is upscaled to this base before crop animation
_OVERSCAN = 1.4  # 40% margin so all motion presets stay within the frame


def ken_burns_filter(
    motion: MotionPreset,
    strength: float,
    duration_sec: float,
    fps: int,
    out_w: int,
    out_h: int,
) -> str:
    """Return an FFmpeg filtergraph string that produces a ken-burns clip.

    Input: a single still image stream (one frame, looped via -loop 1 -t duration).
    Output: a stream of `duration_sec * fps` frames at out_w x out_h.

    `strength` (0..1) scales the magnitude of the motion.
    """
    total_frames = max(1, int(round(duration_sec * fps)))

    # Pre-scale the image so the longest edge is overscan * target dimension,
    # preserving aspect, then center-pad to a canvas large enough to crop from.
    canvas_w = int(out_w * _OVERSCAN)
    canvas_h = int(out_h * _OVERSCAN)

    # 1) scale to fill the canvas (cover semantics — image will be cropped)
    scale = (
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={canvas_w}:{canvas_h}"
    )

    # 2) animated crop expressions
    # n is current frame (0..total_frames-1)
    # progress p = n / (total_frames - 1)  (clamped via min)
    p_expr = f"min(n/{max(total_frames - 1, 1)}, 1)"

    if motion == MotionPreset.STATIC or motion == MotionPreset.GENERATIVE:
        # No animation — just center-crop to output size
        crop_expr = (
            f"crop=w={out_w}:h={out_h}:"
            f"x='(in_w-{out_w})/2':y='(in_h-{out_h})/2'"
        )
        return f"{scale},{crop_expr},setsar=1"

    # Magnitude of motion (in pixels) scales with overscan margin and strength
    margin_x = (canvas_w - out_w) / 2
    margin_y = (canvas_h - out_h) / 2

    if motion == MotionPreset.SLOW_ZOOM_IN:
        # Start at full canvas (zoomed out), end at smaller crop (zoomed in)
        # We animate crop dimensions: large -> small, then ffmpeg pads/scales
        z_start = 1.0
        z_end = 1.0 + 0.18 * strength
        return _zoom_filter(scale, p_expr, z_start, z_end, out_w, out_h, canvas_w, canvas_h)

    if motion == MotionPreset.SLOW_ZOOM_OUT:
        z_start = 1.0 + 0.18 * strength
        z_end = 1.0
        return _zoom_filter(scale, p_expr, z_start, z_end, out_w, out_h, canvas_w, canvas_h)

    if motion == MotionPreset.PUSH_IN:
        # More aggressive zoom with slight bias toward center subject
        z_start = 1.0
        z_end = 1.0 + 0.30 * strength
        return _zoom_filter(scale, p_expr, z_start, z_end, out_w, out_h, canvas_w, canvas_h)

    if motion == MotionPreset.PULL_OUT:
        z_start = 1.0 + 0.30 * strength
        z_end = 1.0
        return _zoom_filter(scale, p_expr, z_start, z_end, out_w, out_h, canvas_w, canvas_h)

    # Pans — animate x or y crop offset
    if motion in (MotionPreset.PAN_LEFT, MotionPreset.PAN_RIGHT):
        travel = margin_x * 1.6 * strength  # how far to pan
        if motion == MotionPreset.PAN_RIGHT:
            x_start = (canvas_w - out_w) / 2 - travel / 2
            x_end = (canvas_w - out_w) / 2 + travel / 2
        else:
            x_start = (canvas_w - out_w) / 2 + travel / 2
            x_end = (canvas_w - out_w) / 2 - travel / 2
        x_expr = f"({x_start})+({p_expr})*({x_end - x_start})"
        crop_expr = (
            f"crop=w={out_w}:h={out_h}:"
            f"x='{x_expr}':y='(in_h-{out_h})/2'"
        )
        return f"{scale},{crop_expr},setsar=1"

    if motion in (MotionPreset.PAN_UP, MotionPreset.PAN_DOWN):
        travel = margin_y * 1.6 * strength
        if motion == MotionPreset.PAN_DOWN:
            y_start = (canvas_h - out_h) / 2 - travel / 2
            y_end = (canvas_h - out_h) / 2 + travel / 2
        else:
            y_start = (canvas_h - out_h) / 2 + travel / 2
            y_end = (canvas_h - out_h) / 2 - travel / 2
        y_expr = f"({y_start})+({p_expr})*({y_end - y_start})"
        crop_expr = (
            f"crop=w={out_w}:h={out_h}:"
            f"x='(in_w-{out_w})/2':y='{y_expr}'"
        )
        return f"{scale},{crop_expr},setsar=1"

    # Fallback — static center crop
    crop_expr = (
        f"crop=w={out_w}:h={out_h}:"
        f"x='(in_w-{out_w})/2':y='(in_h-{out_h})/2'"
    )
    return f"{scale},{crop_expr},setsar=1"


def _zoom_filter(
    base_scale: str,
    p_expr: str,
    z_start: float,
    z_end: float,
    out_w: int,
    out_h: int,
    canvas_w: int,
    canvas_h: int,
) -> str:
    """Animated crop where crop dims shrink/grow, then scale back to out dims."""
    # zoom_t = z_start + p * (z_end - z_start)
    z_expr = f"({z_start})+({p_expr})*({z_end - z_start})"
    # crop dimensions = out / zoom_t (clamped to canvas)
    cw_expr = f"min({out_w}/({z_expr}), {canvas_w})"
    ch_expr = f"min({out_h}/({z_expr}), {canvas_h})"
    cx_expr = f"(in_w-{cw_expr})/2"
    cy_expr = f"(in_h-{ch_expr})/2"
    # crop, then scale back up to exact output size
    return (
        f"{base_scale},"
        f"crop=w='{cw_expr}':h='{ch_expr}':x='{cx_expr}':y='{cy_expr}',"
        f"scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    )
