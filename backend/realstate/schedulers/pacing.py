"""Beat-aware shot pacing — analogous to LTX-Video's RectifiedFlowScheduler.

LTX-Video shifts denoising timesteps based on resolution; we shift shot
boundaries based on tempo. The conceptual move is the same: a domain-specific
scheduler decides *when* events happen.
"""
from __future__ import annotations

import logging
import os
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

        if _snappy_pacing_enabled():
            beat_energies = (
                self._analyze_beat_energy(audio_path, beat_grid, template.target_duration_sec)
                if audio_path
                else {}
            )
            return self._snap_snappy_to_grid(
                template.shot_slots,
                beat_grid,
                template.target_duration_sec,
                beat_energies=beat_energies,
            )

        if template.pacing_mode == PacingMode.BEAT:
            grid = beat_grid
        elif template.pacing_mode == PacingMode.DOWNBEAT:
            grid = beat_grid[::4] if len(beat_grid) >= 4 else beat_grid
        elif template.pacing_mode in (PacingMode.BAR, PacingMode.FREE):
            grid = beat_grid[::8] if len(beat_grid) >= 8 else beat_grid[::4]
        else:
            return self._free(template)

        return self._snap_to_grid(template.shot_slots, grid, template.target_duration_sec)

    def _snap_snappy_to_grid(
        self,
        slots: list[ShotSlot],
        beat_grid: list[float],
        target_duration: float,
        beat_energies: Optional[dict[float, float]] = None,
    ) -> list[ShotTiming]:
        """Create variable, energy-aware beat-locked durations for reel-style edits."""
        if not slots:
            return []

        grid = _grid_with_zero(beat_grid)
        energies = _normalize_energy(beat_energies or {}, grid)
        threshold = _energy_threshold(energies)
        min_sec = _env_float("SNAPPY_MIN_SHOT_SEC", 1.35, low=0.5, high=5.0)
        max_sec = _env_float("SNAPPY_MAX_SHOT_SEC", 3.4, low=min_sec, high=8.0)
        cursor = 0.0
        out: list[ShotTiming] = []

        for index, slot in enumerate(slots):
            remaining = len(slots) - index - 1
            desired = max(min_sec, min(max_sec, float(slot.duration_sec or 0.0)))
            lower = cursor + min_sec
            upper = cursor + max_sec
            if remaining == 0:
                preferred_end = max(lower, min(upper, target_duration))
            else:
                max_end_for_remaining = max(lower, target_duration - remaining * min_sec)
                upper = min(upper, max_end_for_remaining)
                preferred_end = cursor + desired

            end = _best_energy_cut(
                grid=grid,
                energies=energies,
                threshold=threshold,
                cursor=cursor,
                preferred_end=preferred_end,
                lower=lower,
                upper=upper,
            )
            if end is None:
                end = max(lower, min(upper, preferred_end))

            duration = max(0.5, end - cursor)
            out.append(ShotTiming(slot.slot_id, cursor, duration))
            cursor = end

        return out

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

    def _analyze_beat_energy(
        self,
        audio_path: Optional[str],
        beat_grid: list[float],
        target_duration: float,
    ) -> dict[float, float]:
        """Return per-beat RMS energy for only the selected reel window."""
        if not audio_path or not beat_grid:
            return {}
        try:
            import librosa  # type: ignore
            import numpy as np  # type: ignore
        except ImportError:
            log.warning("librosa/numpy not installed — energy-aware cuts disabled")
            return {}

        try:
            duration = max(1.0, float(target_duration))
            y, sr = librosa.load(audio_path, sr=None, mono=True, duration=duration)
            if y is None or len(y) == 0:
                return {}
            hop_length = 512
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
            out: dict[float, float] = {}
            for beat in beat_grid:
                beat = float(beat)
                if beat < 0.0 or beat > duration:
                    continue
                lo = max(0.0, beat - 0.12)
                hi = min(duration, beat + 0.28)
                mask = (times >= lo) & (times <= hi)
                if bool(mask.any()):
                    energy = float(np.mean(rms[mask]))
                else:
                    energy = float(np.interp(beat, times, rms))
                out[round(beat, 6)] = energy
            return out
        except Exception as error:
            log.warning("Beat energy analysis failed: %s", error)
            return {}


def _nearest(grid: list[float], t: float) -> float:
    if not grid:
        return t
    # binary-search-ish; grid is small enough that linear is fine
    return min(grid, key=lambda g: abs(g - t))


def _grid_with_zero(grid: list[float]) -> list[float]:
    cleaned = sorted({round(float(time), 6) for time in grid if float(time) >= 0.0})
    if not cleaned or cleaned[0] > 0.001:
        cleaned.insert(0, 0.0)
    return cleaned


def _nearest_in_range(grid: list[float], target: float, lower: float, upper: float) -> Optional[float]:
    candidates = [time for time in grid if lower <= time <= upper]
    if not candidates:
        return None
    return min(candidates, key=lambda time: (abs(time - target), time))


def _best_energy_cut(
    *,
    grid: list[float],
    energies: dict[float, float],
    threshold: float,
    cursor: float,
    preferred_end: float,
    lower: float,
    upper: float,
) -> Optional[float]:
    candidates = [time for time in grid if lower <= time <= upper]
    if not candidates:
        return None

    high_energy_max = _env_float("SNAPPY_HIGH_ENERGY_MAX_SHOT_SEC", 2.25, low=1.0, high=4.0)
    high_candidates = [
        time
        for time in candidates
        if _energy_at(energies, time) >= threshold and (time - cursor) <= high_energy_max
    ]
    scoring_pool = high_candidates or candidates
    width = max(0.001, upper - lower)
    high_pool = bool(high_candidates)

    def score(time: float) -> tuple[float, float]:
        energy = _energy_at(energies, time)
        proximity = abs(time - preferred_end) / width
        duration = time - cursor
        high_bonus = 0.35 if energy >= threshold else 0.0
        fast_bonus = 0.16 if high_pool and duration <= high_energy_max else 0.0
        # Energy leads, proximity keeps low-energy sections readable instead of random.
        return (energy * 1.45 + high_bonus + fast_bonus - proximity * 0.45, -abs(duration - 2.0))

    return max(scoring_pool, key=score)


def _normalize_energy(raw: dict[float, float], grid: list[float]) -> dict[float, float]:
    if not raw:
        return {}
    values = [float(value) for value in raw.values()]
    low = min(values)
    high = max(values)
    if high <= low:
        return {round(time, 6): 0.5 for time in grid}
    normalized = {
        round(float(time), 6): (float(value) - low) / (high - low)
        for time, value in raw.items()
    }
    return normalized


def _energy_threshold(energies: dict[float, float]) -> float:
    if not energies:
        return 1.1
    values = sorted(energies.values())
    median = values[len(values) // 2]
    buffer = _env_float("SNAPPY_ENERGY_THRESHOLD_BUFFER", 0.08, low=0.0, high=0.5)
    return min(1.0, median + buffer)


def _energy_at(energies: dict[float, float], time: float) -> float:
    if not energies:
        return 0.0
    return float(energies.get(round(float(time), 6), 0.0))


def _snappy_pacing_enabled() -> bool:
    return os.getenv("SNAPPY_BEAT_PACING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float, *, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))
