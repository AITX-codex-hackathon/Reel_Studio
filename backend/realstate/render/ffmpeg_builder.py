"""Translate a Storyboard + RenderConfig into an FFmpeg command.

Strategy:
  1) For each shot, build a per-shot filter chain:
       - loop the still image for the shot duration
       - apply Ken Burns motion
       - apply color grade
       - apply opening fade
     Each shot becomes one labeled output stream like [v0], [v1], ...
  2) For each shot that has a text overlay, pre-render a transparent PNG via
     PIL and add it as an extra input. Composite it onto the shot via `overlay`.
  3) Assemble the shot streams into [vout] using strategy-aware xfade overlaps.
  4) Audio: load each cue file, trim/fade/volume/delay, mix into [aout].
  5) Encode to MP4 with x264 + AAC.

We avoid `drawtext` (requires libfreetype); text overlays are rendered as PNGs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..effects.color_grade import color_grade_filter
from ..effects.ken_burns import ken_burns_filter
from ..effects.text_overlay import overlay_filter_chain, render_overlay_png
from ..models.render_config import RenderConfig
from ..models.shot import TransitionType
from ..models.storyboard import Storyboard

log = logging.getLogger(__name__)

_AUDIO_SAMPLE_RATE = 48_000


@dataclass
class FFmpegCommand:
    args: list[str]
    output_path: str
    expected_duration_sec: float


@dataclass
class TransitionSfxEvent:
    start_sec: float
    duration_sec: float = 1.2
    intensity: str = "calm"
    add_impact: bool = False


class FFmpegBuilder:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", font_path: Optional[str] = None):
        self.ffmpeg = ffmpeg_bin
        self.font_path = font_path

    def build(
        self,
        storyboard: Storyboard,
        config: RenderConfig,
        output_path: Path,
        audio_cue_files: dict[int, str],
        global_color_grade: Optional[str] = None,
        scratch_dir: Optional[Path] = None,
    ) -> FFmpegCommand:
        out_w, out_h = config.output_resolution()
        fps = config.fps
        scratch_dir = scratch_dir or output_path.parent / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        text_overlay_by_id = {o.overlay_id: o for o in storyboard.text_overlays}

        inputs: list[str] = []
        filter_parts: list[str] = []

        # Track input indexes
        shot_input_idx_for: dict[int, int] = {}     # shot index -> ffmpeg -i index
        overlay_input_idx_for: dict[int, int] = {}  # shot index -> ffmpeg -i index for its overlay PNG

        # ---- Build inputs: shots first, then per-shot overlay PNGs ----
        ffmpeg_idx = 0
        for shot_i, shot in enumerate(storyboard.shots):
            inputs.extend([
                "-loop", "1",
                "-t", f"{shot.duration_sec:.3f}",
                "-i", shot.image_path,
            ])
            shot_input_idx_for[shot_i] = ffmpeg_idx
            ffmpeg_idx += 1

        for shot_i, shot in enumerate(storyboard.shots):
            if not (shot.text_overlay_id and shot.rendered_text_overlay):
                continue
            spec = text_overlay_by_id.get(shot.text_overlay_id)
            if not spec:
                continue
            png_path = scratch_dir / f"overlay_shot{shot_i}.png"
            render_overlay_png(
                spec=spec,
                rendered_text=shot.rendered_text_overlay,
                canvas_w=out_w,
                canvas_h=out_h,
                out_path=png_path,
                font_path=self.font_path,
            )
            inputs.extend([
                "-loop", "1",
                "-t", f"{shot.duration_sec:.3f}",
                "-i", str(png_path),
            ])
            overlay_input_idx_for[shot_i] = ffmpeg_idx
            ffmpeg_idx += 1

        # ---- Per-shot video filter chain ----
        for shot_i, shot in enumerate(storyboard.shots):
            chain_steps: list[str] = []

            chain_steps.append(
                ken_burns_filter(
                    motion=shot.motion,
                    strength=shot.motion_strength,
                    duration_sec=shot.duration_sec,
                    fps=fps,
                    out_w=out_w,
                    out_h=out_h,
                )
            )
            chain_steps.append(f"fps={fps},format=yuv420p")

            grade = shot.color_grade or global_color_grade
            cg = color_grade_filter(grade)
            if cg:
                chain_steps.append(cg)

            fade_in_dur = _opening_fade_dur(shot.transition_in)
            if fade_in_dur > 0:
                chain_steps.append(f"fade=t=in:st=0:d={fade_in_dur:.3f}")

            shot_in = shot_input_idx_for[shot_i]
            shot_label = f"v{shot_i}"

            if shot_i in overlay_input_idx_for:
                # Build overlay sub-chain on the PNG stream, then composite.
                spec = text_overlay_by_id[shot.text_overlay_id]
                overlay_dur = min(spec.duration_sec or shot.duration_sec, shot.duration_sec)
                overlay_chain = overlay_filter_chain(
                    overlay_input_label=f"o{shot_i}",
                    overlay_duration_sec=overlay_dur,
                    fade_in_sec=spec.fade_in_sec,
                    fade_out_sec=spec.fade_out_sec,
                )
                ovl_in = overlay_input_idx_for[shot_i]

                # 1) shot chain -> [v{i}_pre]
                pre_chain = ",".join(chain_steps)
                filter_parts.append(f"[{shot_in}:v]{pre_chain}[{shot_label}_pre]")

                # 2) overlay PNG chain -> [o{i}]
                filter_parts.append(f"[{ovl_in}:v]{overlay_chain}[o{shot_i}]")

                # 3) overlay only between t=0..overlay_dur
                enable_expr = f"between(t,0,{overlay_dur:.3f})"
                filter_parts.append(
                    f"[{shot_label}_pre][o{shot_i}]"
                    f"overlay=enable='{enable_expr}':x=0:y=0:format=auto[{shot_label}]"
                )
            else:
                pre_chain = ",".join(chain_steps)
                filter_parts.append(f"[{shot_in}:v]{pre_chain}[{shot_label}]")

        # ---- Optional preview watermark — drawbox with no text (drawtext free) ----
        # We skip an explicit watermark since drawtext is unavailable on minimal builds.
        # The frontend already labels draft renders.

        # ---- Concat ----
        n = len(storyboard.shots)
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")

        # ---- Audio ----
        audio_label = self._build_audio(
            storyboard.audio_cues,
            audio_cue_files,
            ffmpeg_idx,
            inputs,
            filter_parts,
            total_duration_sec=storyboard.total_duration_sec,
        )

        # ---- Assemble command ----
        args = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-stats"]
        args.extend(inputs)

        filter_complex = ";".join(filter_parts)
        args.extend(["-filter_complex", filter_complex])

        args.extend(["-map", "[vout]"])
        if audio_label:
            args.extend(["-map", audio_label])

        args.extend([
            "-c:v", "libx264",
            "-preset", config.preset,
            "-crf", str(config.crf),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-movflags", "+faststart",
        ])

        if audio_label:
            args.extend([
                "-c:a", "aac",
                "-b:a", f"{config.audio_bitrate_kbps}k",
                "-shortest",
            ])

        args.append(str(output_path))

        return FFmpegCommand(
            args=args,
            output_path=str(output_path),
            expected_duration_sec=storyboard.total_duration_sec,
        )

    def _build_audio(
        self,
        cues,
        cue_files: dict[int, str],
        input_offset: int,
        inputs: list[str],
        filter_parts: list[str],
        total_duration_sec: float,
        transition_sfx: Optional[list[TransitionSfxEvent]] = None,
    ) -> Optional[str]:
        added_labels: list[str] = []
        ffmpeg_input_idx = input_offset

        for cue_idx, cue in enumerate(cues):
            file_path = cue_files.get(cue_idx)
            if not file_path:
                continue

            inputs.extend(["-i", file_path])

            start = _quantize_audio_time(max(0.0, cue.start_time_sec))
            end = cue.end_time_sec if cue.end_time_sec is not None else total_duration_sec
            end = _quantize_audio_time(min(end, total_duration_sec))
            cue_dur = _quantize_audio_time(max(0.01, end - start))

            volume_linear = 10 ** (cue.volume_db / 20)
            delay = _audio_delay_expr(start)
            chain = (
                f"atrim=duration={cue_dur:.6f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={cue.fade_in_sec:.3f},"
                f"afade=t=out:st={max(0, cue_dur - cue.fade_out_sec):.3f}:d={cue.fade_out_sec:.3f},"
                f"volume={volume_linear:.4f},"
                f"adelay={delay}|{delay},"
                f"apad=whole_dur={total_duration_sec:.6f}"
            )
            label = f"a{cue_idx}"
            filter_parts.append(f"[{ffmpeg_input_idx}:a]{chain}[{label}]")
            added_labels.append(label)
            ffmpeg_input_idx += 1

        for event_idx, event in enumerate(transition_sfx or []):
            start = _quantize_audio_time(max(0.0, min(event.start_sec, total_duration_sec)))
            duration = _quantize_audio_time(max(0.25, min(event.duration_sec, total_duration_sec - start)))
            if duration <= 0.0:
                continue
            volume = _sfx_volume(event.intensity)
            delay = _audio_delay_expr(start)
            label = f"sfx{event_idx}"
            filter_parts.append(
                f"anoisesrc=color=pink:r=48000:d={duration:.6f},"
                "highpass=f=450,lowpass=f=6200,"
                f"afade=t=in:st=0:d={min(0.25, duration / 3):.3f},"
                f"afade=t=out:st={max(0, duration - min(0.45, duration / 2)):.3f}:d={min(0.45, duration / 2):.3f},"
                f"volume={volume:.4f},"
                f"adelay={delay}|{delay},apad=whole_dur={total_duration_sec:.6f}"
                f"[{label}]"
            )
            added_labels.append(label)
            if event.add_impact:
                impact_start = _quantize_audio_time(max(0.0, min(start + duration * 0.72, total_duration_sec)))
                impact_delay = _audio_delay_expr(impact_start)
                impact_label = f"sfxhit{event_idx}"
                filter_parts.append(
                    "sine=frequency=74:sample_rate=48000:duration=0.280,"
                    "afade=t=out:st=0.080:d=0.200,"
                    f"volume={min(0.18, volume * 0.55):.4f},"
                    f"adelay={impact_delay}|{impact_delay},"
                    f"apad=whole_dur={total_duration_sec:.6f}"
                    f"[{impact_label}]"
                )
                added_labels.append(impact_label)

        if not added_labels:
            return None

        bed_label = "asilence"
        filter_parts.append(f"anullsrc=r={_AUDIO_SAMPLE_RATE}:cl=stereo:d={total_duration_sec:.6f}[{bed_label}]")
        mix_labels = [bed_label, *added_labels]
        mix_in = "".join(f"[{label}]" for label in mix_labels)
        filter_parts.append(
            f"{mix_in}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0,"
            f"atrim=duration={total_duration_sec:.6f},asetpts=PTS-STARTPTS[aout]"
        )
        return "[aout]"


    def build_from_clips(
        self,
        shots: list,
        config: RenderConfig,
        output_path: Path,
        audio_cue_files: dict[int, str],
        total_duration_sec: float,
        audio_cues: Optional[list] = None,
        beat_timestamps: Optional[list[float]] = None,
        transition_sfx: Optional[list[TransitionSfxEvent]] = None,
    ) -> FFmpegCommand:
        """Build FFmpeg command from pre-rendered FAL video clips.

        Each shot must have video_clip_path set. Clips are trimmed to their
        duration, eased according to the agent's ramp profile, and assembled
        with edit-strategy overlaps. Beat timestamps are accepted upstream for
        timing and sound design.
        """
        out_w, out_h = config.output_resolution()
        fps = config.fps

        inputs: list[str] = []
        filter_parts: list[str] = []

        valid_shots = [s for s in shots if s.video_clip_path]
        shot_durations = [_shot_duration_sec(shot, fps) for shot in valid_shots]
        for i, shot in enumerate(valid_shots):
            inputs.extend(["-i", shot.video_clip_path])
            trim_dur = shot_durations[i]
            handle_sec = _clip_handle_sec(shot, fps)
            ramp_sec = _ramp_sec(shot, trim_dur)
            trim_start = handle_sec if handle_sec > 0 else 0.0
            # Scale to target resolution, trim to shot duration
            chain_steps = [
                f"trim=start={trim_start:.3f}:duration={trim_dur:.3f}",
                "setpts=PTS-STARTPTS",
            ]
            ramp = _s_curve_setpts_filter(trim_dur, ramp_sec)
            if ramp:
                chain_steps.append(ramp)
            chain_steps.extend([
                f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase",
                f"crop={out_w}:{out_h}",
                f"fps={fps}",
                "settb=AVTB",
            ])
            blur = _motion_blur_filter(shot)
            if blur:
                chain_steps.append(blur)
            chain_steps.extend([
                "format=yuv420p",
            ])
            filter_parts.append(
                f"[{i}:v]{','.join(chain_steps)}[v{i}]"
            )

        n = len(valid_shots)
        if n == 0:
            raise ValueError("No clips with video_clip_path to assemble")

        timeline_duration_sec = _timeline_duration(valid_shots, fps)
        if n == 1:
            filter_parts.append("[v0]null[vout]")
        else:
            prev_label = "v0"
            current_duration = shot_durations[0]
            for i in range(1, n):
                next_duration = shot_durations[i]
                overlap = _transition_overlap_sec(valid_shots[i - 1], valid_shots[i], fps)
                out_label = f"vx{i}"
                if overlap <= 0.0:
                    filter_parts.append(f"[{prev_label}][v{i}]concat=n=2:v=1:a=0[{out_label}]")
                    current_duration = current_duration + next_duration
                else:
                    overlap = max(0.0, min(overlap, current_duration - 0.05, next_duration - 0.05))
                    if overlap <= 0.0:
                        filter_parts.append(f"[{prev_label}][v{i}]concat=n=2:v=1:a=0[{out_label}]")
                        current_duration = current_duration + next_duration
                    else:
                        offset = max(0.0, current_duration - overlap)
                        transition = _xfade_transition(valid_shots[i - 1], valid_shots[i])
                        filter_parts.append(
                            f"[{prev_label}][v{i}]"
                            f"xfade=transition={transition}:duration={overlap:.3f}:offset={offset:.3f}"
                            f"[{out_label}]"
                        )
                        current_duration = current_duration + next_duration - overlap
                prev_label = out_label
            filter_parts.append(f"[{prev_label}]format=yuv420p[vout]")

        audio_label = self._build_audio(
            cues=audio_cues or [],
            cue_files=audio_cue_files,
            input_offset=n,
            inputs=inputs,
            filter_parts=filter_parts,
            total_duration_sec=timeline_duration_sec,
            transition_sfx=transition_sfx,
        )

        args = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-stats"]
        args.extend(inputs)
        args.extend(["-filter_complex", ";".join(filter_parts)])
        args.extend(["-map", "[vout]"])
        if audio_label:
            args.extend(["-map", audio_label])

        args.extend([
            "-c:v", "libx264",
            "-preset", config.preset,
            "-crf", str(config.crf),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-movflags", "+faststart",
        ])
        if audio_label:
            args.extend(["-c:a", "aac", "-b:a", f"{config.audio_bitrate_kbps}k", "-shortest"])

        args.append(str(output_path))
        return FFmpegCommand(
            args=args,
            output_path=str(output_path),
            expected_duration_sec=timeline_duration_sec,
        )


def _opening_fade_dur(t: TransitionType) -> float:
    return {
        TransitionType.CUT: 0.0,
        TransitionType.DISSOLVE: 0.4,
        TransitionType.FADE: 0.7,
        TransitionType.SLIDE_LEFT: 0.0,
        TransitionType.SLIDE_RIGHT: 0.0,
        TransitionType.WHIP_PAN: 0.0,
    }.get(t, 0.0)


def _sfx_volume(intensity: str) -> float:
    return {
        "calm": 0.035,
        "moderate": 0.065,
        "fast": 0.100,
    }.get((intensity or "calm").lower(), 0.045)


def _audio_delay_expr(seconds: float) -> str:
    samples = max(0, int(round(seconds * _AUDIO_SAMPLE_RATE)))
    return f"{samples}S"


def _quantize_audio_time(seconds: float) -> float:
    return max(0.0, round(float(seconds) * _AUDIO_SAMPLE_RATE) / _AUDIO_SAMPLE_RATE)


def _quantize_video_time(seconds: float, fps: int) -> float:
    frame_count = max(0, int(round(float(seconds) * max(fps, 1))))
    return _quantize_audio_time(frame_count / max(fps, 1))


def _shot_duration_sec(shot, fps: int) -> float:
    try:
        duration = float(getattr(shot, "duration_sec", 0.01) or 0.01)
    except (TypeError, ValueError):
        duration = 0.01
    return max(1.0 / max(fps, 1), _quantize_video_time(duration, fps))


def _clip_handle_sec(shot, fps: int) -> float:
    try:
        handle = max(0.0, min(1.0, float(getattr(shot, "trim_handle_sec", 0.0) or 0.0)))
        return _quantize_video_time(handle, fps)
    except (TypeError, ValueError):
        return 0.0


def _ramp_sec(shot, duration_sec: float) -> float:
    if getattr(shot, "is_transition_bridge", False):
        return 0.0
    if duration_sec < 2.0:
        return 0.0
    try:
        configured = float(getattr(shot, "velocity_ramp_sec", 0.0) or 0.0)
    except (TypeError, ValueError):
        configured = 0.0
    if configured <= 0:
        profile = str(getattr(shot, "ramp_profile", "") or "").lower()
        configured = {
            "cruise": 0.0,
            "reveal": 0.65,
            "impact": 0.75,
        }.get(profile, 0.5)
    return max(0.0, min(configured, duration_sec / 3))


def _motion_blur_filter(shot) -> str:
    strategy = _intent_strategy(shot)
    intensity = str(getattr(shot, "movement_intensity", "") or "").lower()
    if strategy == "whip_pan" or intensity == "fast":
        return "tmix=frames=3:weights='1 2 1'"
    return ""


def _timeline_duration(shots: list, fps: int) -> float:
    if not shots:
        return 0.0
    current = _shot_duration_sec(shots[0], fps)
    for i in range(1, len(shots)):
        next_duration = _shot_duration_sec(shots[i], fps)
        overlap = _transition_overlap_sec(shots[i - 1], shots[i], fps)
        if overlap > 0.0:
            overlap = max(0.0, min(overlap, current - 0.05, next_duration - 0.05))
        current = current + next_duration - max(0.0, overlap)
    return max(0.01, current)


def _transition_overlap_sec(prev_shot, next_shot, fps: int) -> float:
    if getattr(prev_shot, "is_transition_bridge", False) or getattr(next_shot, "is_transition_bridge", False):
        return 0.0
    strategy = _intent_strategy(prev_shot)
    if strategy == "match_cut":
        return _quantize_video_time(0.5, fps)
    if strategy == "whip_pan":
        return _quantize_video_time(0.35, fps)
    if strategy == "reveal":
        return _quantize_video_time(0.20, fps)
    if strategy == "handshake":
        return _quantize_video_time(0.12, fps)
    return 0.0


def _xfade_transition(prev_shot, next_shot) -> str:
    # Keep to widely supported transitions; motion blur and SFX carry the whip/reveal intent.
    return "fade"


def _intent_strategy(shot) -> str:
    logic = getattr(shot, "transition_logic", None)
    if isinstance(logic, dict):
        strategy = _normalize_strategy(logic.get("strategy"))
        if strategy:
            return strategy
    return _normalize_strategy(getattr(shot, "bridge_strategy", None)) or "simple_cut"


def _normalize_strategy(value) -> str:
    strategy = str(value or "").strip().lower()
    if strategy in {"handshake", "reveal", "whip_pan", "simple_cut", "match_cut"}:
        return strategy
    return {
        "flfv_bridge": "handshake",
        "whip_pan_blur": "whip_pan",
        "dissolve": "match_cut",
        "cut": "simple_cut",
        "skip": "simple_cut",
        "none": "simple_cut",
    }.get(strategy, "")


def _s_curve_setpts_filter(duration_sec: float, ramp_sec: float) -> str:
    """Cubic timestamp easing at clip boundaries while keeping endpoints fixed."""
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
