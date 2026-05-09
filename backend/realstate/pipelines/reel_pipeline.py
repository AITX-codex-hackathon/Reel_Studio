"""ReelPipeline — FAL clip generation → audio → FFmpeg assembly."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from ..data.style_recipes import get_by_id, get_for_room
from ..integrations.elevenlabs import ElevenLabsClient
from ..integrations.fal_client import FalClient
from ..integrations.stock_audio import StockAudioLibrary
from ..models.render_config import RenderConfig
from ..models.storyboard import Storyboard
from ..models.template import AudioCue
from ..render.encoder import Encoder, RenderProgress
from ..render.ffmpeg_builder import FFmpegBuilder

log = logging.getLogger(__name__)


@dataclass
class RenderResult:
    output_path: Path
    duration_sec: float


class ReelPipeline:
    def __init__(
        self,
        builder: Optional[FFmpegBuilder] = None,
        encoder: Optional[Encoder] = None,
        stock_audio: Optional[StockAudioLibrary] = None,
        elevenlabs: Optional[ElevenLabsClient] = None,
        fal: Optional[FalClient] = None,
        font_path: Optional[str] = None,
    ):
        self.builder = builder or FFmpegBuilder(font_path=font_path)
        self.encoder = encoder or Encoder()
        self.stock_audio = stock_audio or StockAudioLibrary()
        self.elevenlabs = elevenlabs or ElevenLabsClient()
        self.fal = fal or FalClient()

    async def render(
        self,
        storyboard: Storyboard,
        config: RenderConfig,
        output_path: Path,
        global_color_grade: Optional[str] = None,
        scratch_dir: Optional[Path] = None,
    ) -> AsyncIterator[RenderProgress]:
        scratch = scratch_dir or output_path.parent / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)

        shots = list(storyboard.shots)
        n = len(shots)

        # ── Phase 1: FAL clip generation (0 → 0.70) ──────────────────────────
        if self.fal.enabled and n > 0:
            log.info("Generating %d FAL clips…", n)
            for i, shot in enumerate(shots):
                yield RenderProgress(progress=i / n * 0.70, seconds_done=0.0, fps=0.0)

                clip_path = scratch / f"clip_{i:02d}_{shot.slot_id}.mp4"

                recipe = (
                    get_by_id(shot.style_recipe_id)
                    if shot.style_recipe_id
                    else get_for_room(shot.room_type, seed=i)
                )
                prompt = (
                    recipe.video_prompt
                    if recipe
                    else "cinematic smooth camera movement, luxury real estate photography"
                )

                if shot.image_path and Path(shot.image_path).exists():
                    clip = await self.fal.image_to_video(
                        image_path=Path(shot.image_path),
                        prompt=prompt,
                        out_path=clip_path,
                    )
                else:
                    clip = await self.fal.text_to_video(
                        prompt=prompt,
                        out_path=clip_path,
                    )

                if clip:
                    shots[i] = shot.model_copy(update={"video_clip_path": str(clip)})
                else:
                    log.warning("FAL failed for shot %s — will skip", shot.slot_id)

            yield RenderProgress(progress=0.70, seconds_done=0.0, fps=0.0)
        else:
            log.info("FAL disabled or no shots — falling back to Ken Burns render")

        # ── Phase 2: Audio (0.70 → 0.75) ────────────────────────────────────
        total_dur = sum(s.duration_sec for s in shots)
        cue_files = await self._resolve_audio_cues(
            storyboard.audio_cues,
            scratch,
            seed=config.seed,
            total_duration_sec=total_dur,
        )
        yield RenderProgress(progress=0.75, seconds_done=0.0, fps=0.0)

        # ── Phase 3: FFmpeg assembly (0.75 → 1.0) ────────────────────────────
        clips_ready = [s for s in shots if s.video_clip_path]

        if clips_ready:
            cmd = self.builder.build_from_clips(
                shots=clips_ready,
                config=config,
                output_path=output_path,
                audio_cue_files=cue_files,
                total_duration_sec=sum(s.duration_sec for s in clips_ready),
                audio_cues=storyboard.audio_cues,
                beat_timestamps=storyboard.beat_timestamps or [],
            )
        else:
            # No FAL clips — fall back to Ken Burns on stills
            updated = storyboard.model_copy(update={"shots": shots, "text_overlays": []})
            cmd = self.builder.build(
                storyboard=updated,
                config=config,
                output_path=output_path,
                audio_cue_files=cue_files,
                global_color_grade=global_color_grade,
            )

        log.info("FFmpeg: %s … %s", " ".join(cmd.args[:4]), cmd.args[-1])
        async for progress in self.encoder.run(cmd):
            yield RenderProgress(
                progress=0.75 + 0.25 * progress.progress,
                seconds_done=progress.seconds_done,
                fps=progress.fps,
            )

    async def _resolve_audio_cues(
        self,
        cues: list[AudioCue],
        scratch_dir: Path,
        seed: int,
        total_duration_sec: float,
    ) -> dict[int, str]:
        out: dict[int, str] = {}
        for i, cue in enumerate(cues):
            q = cue.track_query.strip()
            file_path: Optional[Path] = None

            if q.startswith("gen:"):
                if cue.kind == "voiceover":
                    file_path = await self.elevenlabs.tts(
                        text=q[4:].strip(),
                        out_path=scratch_dir / f"voice_{i}.mp3",
                    )
                else:
                    file_path = await self.elevenlabs.music(
                        prompt=q[4:].strip(),
                        out_path=scratch_dir / f"music_{i}.mp3",
                        duration_sec=min(total_duration_sec, 60.0),
                    )
            else:
                track = self.stock_audio.find(q, seed=seed)
                if track:
                    file_path = track.path

            if file_path:
                out[i] = str(file_path)
            else:
                log.info("Cue %d (%s) — no audio found, skipping", i, q[:40])

        return out
