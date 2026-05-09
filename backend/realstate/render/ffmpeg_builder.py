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
  3) Concatenate the shot streams into [vout].
  4) Audio: load each cue file, trim/fade/volume/delay, mix into [aout].
  5) Encode to MP4 with x264 + AAC.

We avoid `drawtext` (requires libfreetype) and `xfade` (offset bookkeeping is
brittle); fades are handled with the `fade` filter at clip boundaries.
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


@dataclass
class FFmpegCommand:
    args: list[str]
    output_path: str
    expected_duration_sec: float


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
    ) -> Optional[str]:
        if not cues or not cue_files:
            return None

        added_labels: list[str] = []
        ffmpeg_input_idx = input_offset

        for cue_idx, cue in enumerate(cues):
            file_path = cue_files.get(cue_idx)
            if not file_path:
                continue

            inputs.extend(["-i", file_path])

            start = max(0.0, cue.start_time_sec)
            end = cue.end_time_sec if cue.end_time_sec is not None else total_duration_sec
            end = min(end, total_duration_sec)
            cue_dur = max(0.01, end - start)

            volume_linear = 10 ** (cue.volume_db / 20)
            chain = (
                f"atrim=duration={cue_dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={cue.fade_in_sec:.3f},"
                f"afade=t=out:st={max(0, cue_dur - cue.fade_out_sec):.3f}:d={cue.fade_out_sec:.3f},"
                f"volume={volume_linear:.4f},"
                f"adelay={int(start * 1000)}|{int(start * 1000)},"
                f"apad=whole_dur={total_duration_sec:.3f}"
            )
            label = f"a{cue_idx}"
            filter_parts.append(f"[{ffmpeg_input_idx}:a]{chain}[{label}]")
            added_labels.append(label)
            ffmpeg_input_idx += 1

        if not added_labels:
            return None

        if len(added_labels) == 1:
            filter_parts.append(
                f"[{added_labels[0]}]atrim=duration={total_duration_sec:.3f}[aout]"
            )
        else:
            mix_in = "".join(f"[{label}]" for label in added_labels)
            filter_parts.append(
                f"{mix_in}amix=inputs={len(added_labels)}:duration=longest:dropout_transition=0,"
                f"atrim=duration={total_duration_sec:.3f}[aout]"
            )
        return "[aout]"


def _opening_fade_dur(t: TransitionType) -> float:
    return {
        TransitionType.CUT: 0.0,
        TransitionType.DISSOLVE: 0.4,
        TransitionType.FADE: 0.7,
        TransitionType.SLIDE_LEFT: 0.0,
        TransitionType.SLIDE_RIGHT: 0.0,
        TransitionType.WHIP_PAN: 0.0,
    }.get(t, 0.0)
