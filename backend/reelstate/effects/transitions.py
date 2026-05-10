"""Transitions between shots using FFmpeg's xfade filter."""
from __future__ import annotations

from ..models.shot import TransitionType

# Map our TransitionType to xfade transition names
# https://trac.ffmpeg.org/wiki/Xfade
XFADE_MAP: dict[TransitionType, str] = {
    TransitionType.CUT: "fade",  # zero-duration fade ≈ cut
    TransitionType.DISSOLVE: "fade",
    TransitionType.SLIDE_LEFT: "slideleft",
    TransitionType.SLIDE_RIGHT: "slideright",
    TransitionType.WHIP_PAN: "wipeleft",
    TransitionType.FADE: "fadeblack",
}

# How long each transition takes (seconds). Cuts are 0.
DEFAULT_DURATION: dict[TransitionType, float] = {
    TransitionType.CUT: 0.0,
    TransitionType.DISSOLVE: 0.5,
    TransitionType.SLIDE_LEFT: 0.4,
    TransitionType.SLIDE_RIGHT: 0.4,
    TransitionType.WHIP_PAN: 0.25,
    TransitionType.FADE: 0.8,
}


def transition_xfade(
    transition: TransitionType,
    offset_sec: float,
) -> tuple[str, float]:
    """Return (xfade filter args, transition_duration_sec).

    `offset_sec` is the absolute time on the *outgoing* clip where the transition begins.
    The filter is meant to be applied like:
        [a][b]xfade=transition=fade:duration=0.5:offset=4.5[ab]
    """
    name = XFADE_MAP.get(transition, "fade")
    dur = DEFAULT_DURATION.get(transition, 0.0)
    if dur <= 0:
        # Cut — degenerate xfade with tiny duration so concat semantics still hold
        # We use a 1-frame fade to satisfy ffmpeg's positive-duration requirement
        return f"transition={name}:duration=0.04:offset={offset_sec:.3f}", 0.0
    return f"transition={name}:duration={dur:.3f}:offset={offset_sec:.3f}", dur
