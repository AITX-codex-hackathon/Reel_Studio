"""ReelPipeline — FAL clip generation → audio → FFmpeg assembly."""
from __future__ import annotations

import logging
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from ..data.style_recipes import get_by_id, get_cinematic_for_room
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
            concurrency = max(1, min(n, int(os.getenv("FAL_RENDER_CONCURRENCY", "3"))))
            log.info("Generating %d FAL clips with concurrency=%d", n, concurrency)
            semaphore = asyncio.Semaphore(concurrency)
            event_queue: asyncio.Queue[RenderProgress] = asyncio.Queue()

            async def generate_one(i: int):
                async with semaphore:
                    shot = shots[i]
                    await event_queue.put(
                        RenderProgress(
                            progress=0.0,
                            seconds_done=0.0,
                            fps=0.0,
                            phase="fal",
                            message=f"Generating shot {i + 1} of {n}: {shot.slot_id.replace('_', ' ')}.",
                            current=i + 1,
                            total=n,
                            shot_id=shot.slot_id,
                        )
                    )
                    clip_path = scratch / f"clip_{i:02d}_{shot.slot_id}.mp4"

                    recipe = (
                        get_by_id(shot.style_recipe_id)
                        if shot.style_recipe_id
                        else get_cinematic_for_room(
                            shot.room_type,
                            seed=i,
                            intent=" ".join(
                                part
                                for part in [
                                    shot.scene_purpose or "",
                                    shot.style_notes or "",
                                    shot.transition_plan or "",
                                ]
                                if part
                            ),
                        )
                    )
                    prompt = _fal_provider_prompt(storyboard=storyboard, shot=shot, recipe=recipe)

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
                    return i, clip

            completed = 0
            tasks = {asyncio.create_task(generate_one(i)) for i in range(n)}
            yield RenderProgress(
                progress=0.0,
                seconds_done=0.0,
                fps=0.0,
                phase="fal",
                message=f"Queued {n} cinematic FAL clip job{'s' if n != 1 else ''} with concurrency {concurrency}.",
                total=n,
            )
            while tasks:
                while not event_queue.empty():
                    event = await event_queue.get()
                    event.progress = completed / n * 0.70
                    yield event

                done, tasks = await asyncio.wait(tasks, timeout=0.25, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    i, clip = await task
                    completed += 1
                    if clip:
                        shots[i] = shots[i].model_copy(update={"video_clip_path": str(clip)})
                        message = f"Finished shot {completed} of {n}: {shots[i].slot_id.replace('_', ' ')}."
                    else:
                        log.warning("FAL failed for shot %s — will skip", shots[i].slot_id)
                        message = f"Shot {shots[i].slot_id.replace('_', ' ')} failed in FAL; continuing with available clips."
                    yield RenderProgress(
                        progress=completed / n * 0.70,
                        seconds_done=0.0,
                        fps=0.0,
                        phase="fal",
                        message=message,
                        current=completed,
                        total=n,
                        shot_id=shots[i].slot_id,
                    )

            yield RenderProgress(
                progress=0.70,
                seconds_done=0.0,
                fps=0.0,
                phase="fal",
                message="All available shot clips are ready.",
                current=n,
                total=n,
            )
        else:
            log.info("FAL disabled or no shots — falling back to Ken Burns render")
            yield RenderProgress(
                progress=0.05,
                seconds_done=0.0,
                fps=0.0,
                phase="fallback",
                message="FAL is disabled or no shots are available; using still-photo motion fallback.",
            )

        # ── Phase 2: Audio (0.70 → 0.75) ────────────────────────────────────
        total_dur = sum(s.duration_sec for s in shots)
        yield RenderProgress(
            progress=0.71,
            seconds_done=0.0,
            fps=0.0,
            phase="audio",
            message="Preparing music, fades, and audio timing.",
        )
        cue_files = await self._resolve_audio_cues(
            storyboard.audio_cues,
            scratch,
            seed=config.seed,
            total_duration_sec=total_dur,
        )
        yield RenderProgress(
            progress=0.75,
            seconds_done=0.0,
            fps=0.0,
            phase="audio",
            message="Audio is ready. Stitching the final reel next.",
        )

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
        yield RenderProgress(
            progress=0.76,
            seconds_done=0.0,
            fps=0.0,
            phase="stitching",
            message="Stitching clips, transitions, overlays, and music into the reel.",
        )
        async for progress in self.encoder.run(cmd):
            yield RenderProgress(
                progress=0.75 + 0.25 * progress.progress,
                seconds_done=progress.seconds_done,
                fps=progress.fps,
                phase="stitching",
                message=(
                    f"Stitching final reel: {progress.seconds_done:.1f}s encoded."
                    if progress.seconds_done
                    else "Stitching final reel."
                ),
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
            elif q.startswith("file:"):
                candidate = Path(q[5:].strip()).expanduser()
                if candidate.exists() and candidate.is_file():
                    file_path = candidate
                else:
                    log.info("Cue %d file path missing — skipping: %s", i, candidate)
            else:
                track = self.stock_audio.find(q, seed=seed)
                if track:
                    file_path = track.path

            if file_path:
                out[i] = str(file_path)
            else:
                log.info("Cue %d (%s) — no audio found, skipping", i, q[:40])

        return out


def _fal_provider_prompt(storyboard: Storyboard, shot, recipe) -> str:
    """Compact FAL-facing prompt; the full storyboard keeps richer agent notes."""
    brief = storyboard.creative_brief
    recipe_line = ""
    if recipe:
        recipe_line = (
            f"Recipe {recipe.style_id}: {recipe.category}; mood {recipe.mood}; "
            f"motion {recipe.camera_motion}; dynamics {recipe.environmental_dynamics}; {recipe.video_prompt}"
        )
    parts = [
        "Premium real-estate image-to-video. Preserve the source image as visual truth.",
        (
            f"Binding concept: {brief.concept_title}. {brief.logline}"
            if brief and (brief.concept_title or brief.logline)
            else ""
        ),
        f"Scene purpose: {shot.scene_purpose}" if shot.scene_purpose else "",
        f"Camera: {shot.motion.value if hasattr(shot.motion, 'value') else shot.motion}, strength {shot.motion_strength:.2f}.",
        recipe_line,
        f"Direction: {shot.style_notes}" if shot.style_notes else "",
        f"User prompt/custom direction: {shot.style_recipe_prompt}" if shot.style_recipe_prompt else "",
        f"Beat plan: {shot.beat_plan}" if shot.beat_plan else "",
        f"Mask plan: {shot.masking_plan}" if shot.masking_plan else "",
        f"Transition: {shot.transition_plan}" if shot.transition_plan else "",
        f"Continuity: {shot.continuity_notes}" if shot.continuity_notes else "",
        f"Rubric: {_rubric_provider_text(shot.rubric_plan)}" if shot.rubric_plan else "",
        (
            f"Music: {brief.music_strategy}"
            if brief and brief.music_strategy
            else "Music: calm commercial dramatic pacing; cuts breathe on downbeats."
        ),
        (
            "Hard negatives: no new rooms, no impossible architecture, no warped walls or fixtures, "
            "no added people, no readable text changes, no logos, no watermarks, no trap/hype/chaotic whip energy."
        ),
    ]
    return _compact_prompt(parts, max_chars=2350)


def _rubric_provider_text(rubric_plan) -> str:
    if not isinstance(rubric_plan, dict):
        return ""
    raw_user_edit = rubric_plan.get("RAW_USER_RUBRIC_EDIT")
    if raw_user_edit:
        return f"User rubric/custom scene note: {' '.join(str(raw_user_edit).split())[:1200]}"
    priority = [
        "NARRATIVE_THESIS",
        "TEMPORAL_AUDIO_SYNC",
        "OPTICS_AND_RIGGING",
        "KINETIC_PATHWAY",
        "PRESERVATION_AND_MASKING",
        "SEAMLESS_TRANSITION_ARCHITECTURE",
        "FAL_GENERATION_PROMPT",
    ]
    parts: list[str] = []
    for key in priority:
        item = rubric_plan.get(key)
        if not item:
            continue
        if isinstance(item, dict):
            parts.append(f"{key}: " + "; ".join(f"{nested_key}={nested_value}" for nested_key, nested_value in item.items()))
        else:
            parts.append(f"{key}: {item}")
    return " ".join(parts)


def _compact_prompt(parts: list[str], max_chars: int) -> str:
    out = ""
    for part in parts:
        text = " ".join(str(part or "").split())
        if not text:
            continue
        addition = f"{text} "
        if len(out) + len(addition) <= max_chars:
            out += addition
            continue
        remaining = max_chars - len(out) - 1
        if remaining > 80:
            out += text[:remaining].rstrip() + " "
        break
    return out.strip()
