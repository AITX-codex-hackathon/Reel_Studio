"""Beat-aware shot pacing — analogous to LTX-Video's RectifiedFlowScheduler.

LTX-Video shifts denoising timesteps based on resolution; we shift shot
boundaries based on tempo. The conceptual move is the same: a domain-specific
scheduler decides *when* events happen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..models.shot import ShotSlot
from ..models.template import PacingMode, Template

log = logging.getLogger(__name__)


@dataclass
class ShotTiming:
    slot_id: str
    start_time_sec: float
    duration_sec: float


class PacingScheduler:
    """Computes shot start times and durations from a template + (optionally) audio analysis."""

    def schedule(
        self,
        template: Template,
        audio_path: Optional[str] = None,
        beat_timestamps_ms: Optional[list[int]] = None,
    ) -> list[ShotTiming]:
        has_audio_grid = bool(beat_timestamps_ms) or bool(audio_path)
        if template.pacing_mode == PacingMode.FREE and not has_audio_grid:
            return self._free(template)

        if beat_timestamps_ms:
            beat_grid = [ms / 1000 for ms in beat_timestamps_ms]
        elif audio_path:
            _bpm, beat_grid = self._analyze_beats(audio_path)
        else:
            return self._free(template)

        if not beat_grid:
            log.info("Beat detection unavailable; falling back to free pacing")
            return self._free(template)

        if template.pacing_mode == PacingMode.BEAT:
            grid = beat_grid
        elif template.pacing_mode == PacingMode.DOWNBEAT:
            grid = beat_grid[::4] if len(beat_grid) >= 4 else beat_grid
        elif template.pacing_mode in (PacingMode.BAR, PacingMode.FREE):
            grid = beat_grid[::8] if len(beat_grid) >= 8 else beat_grid[::4]
        else:
            return self._free(template)

        return self._snap_to_grid(template.shot_slots, grid, template.target_duration_sec)

    def _free(self, template: Template) -> list[ShotTiming]:
        """Use template-defined durations as-is, accumulating start times."""
        timings: list[ShotTiming] = []
        t = 0.0
        for slot in template.shot_slots:
            timings.append(ShotTiming(slot.slot_id, t, slot.duration_sec))
            t += slot.duration_sec
        return timings

    def _snap_to_grid(
        self,
        slots: list[ShotSlot],
        grid: list[float],
        target_duration: float,
    ) -> list[ShotTiming]:
        """Snap each shot boundary to the nearest grid point."""
        # Start with template-defined start times
        timings = self._free_for_slots(slots)

        snapped: list[ShotTiming] = []
        for t in timings:
            snapped_start = _nearest(grid, t.start_time_sec)
            snapped.append(ShotTiming(t.slot_id, snapped_start, t.duration_sec))

        # Recompute durations from snapped starts
        out: list[ShotTiming] = []
        for i, t in enumerate(snapped):
            if i + 1 < len(snapped):
                dur = max(0.5, snapped[i + 1].start_time_sec - t.start_time_sec)
            else:
                dur = max(0.5, target_duration - t.start_time_sec)
            out.append(ShotTiming(t.slot_id, t.start_time_sec, dur))
        return out

    def _free_for_slots(self, slots: list[ShotSlot]) -> list[ShotTiming]:
        timings = []
        t = 0.0
        for slot in slots:
            timings.append(ShotTiming(slot.slot_id, t, slot.duration_sec))
            t += slot.duration_sec
        return timings

    def _analyze_beats(self, audio_path: str) -> tuple[float, list[float]]:
        """Return (bpm, beat_times). Falls back to (0, []) if librosa unavailable."""
        try:
            import librosa  # type: ignore
        except ImportError:
            log.warning("librosa not installed — beat detection disabled")
            return 0.0, []

        try:
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
            return float(tempo), [float(t) for t in beat_times]
        except Exception as e:
            log.warning("Beat detection failed: %s", e)
            return 0.0, []


def _nearest(grid: list[float], t: float) -> float:
    if not grid:
        return t
    # binary-search-ish; grid is small enough that linear is fine
    return min(grid, key=lambda g: abs(g - t))
