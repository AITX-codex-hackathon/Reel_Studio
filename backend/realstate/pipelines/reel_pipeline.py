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
from ..render.ffmpeg_builder import FFmpegBuilder, TransitionSfxEvent
from ..render.post_process import cook_transition_bridge

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

        shots = _snap_shots_to_audio_grid(list(storyboard.shots), storyboard.beat_timestamps or [])
        n = len(shots)
        transition_bridge_clips: dict[int, Path] = {}
        transition_bridge_durations: dict[int, float] = {}
        transition_duration_sec = self.fal.transition_duration_sec
        scene_handle_sec = _scene_handle_sec()
        motion_preroll_trim_sec = _motion_preroll_trim_sec()

        # ── Phase 1: FAL clip generation (0 → 0.70) ──────────────────────────
        if self.fal.enabled and n > 0:
            concurrency = max(1, min(n, int(os.getenv("FAL_RENDER_CONCURRENCY", "3"))))
            bridge_pairs = _transition_bridge_pairs(shots) if self.fal.transition_bridges_enabled else []
            main_progress_end = 0.52 if bridge_pairs else 0.70
            log.info(
                "Generating %d FAL clips and %d transition bridges with concurrency=%d",
                n,
                len(bridge_pairs),
                concurrency,
            )
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
                    prompt = _fal_provider_prompt(
                        storyboard=storyboard,
                        shot=shot,
                        recipe=recipe,
                        prev_shot=shots[i - 1] if i > 0 else None,
                        next_shot=shots[i + 1] if i + 1 < n else None,
                    )

                    if shot.image_path and Path(shot.image_path).exists():
                        clip = await self.fal.image_to_video(
                            image_path=Path(shot.image_path),
                            prompt=prompt,
                            out_path=clip_path,
                            duration_sec=shot.duration_sec + scene_handle_sec * 2 + motion_preroll_trim_sec,
                        )
                    else:
                        clip = await self.fal.text_to_video(
                            prompt=prompt,
                            out_path=clip_path,
                            duration_sec=shot.duration_sec + scene_handle_sec * 2 + motion_preroll_trim_sec,
                        )
                    return i, clip

            completed = 0
            tasks = {asyncio.create_task(generate_one(i)) for i in range(n)}
            yield RenderProgress(
                progress=0.0,
                seconds_done=0.0,
                fps=0.0,
                phase="fal",
                message=(
                    f"Queued {n} cinematic FAL clip job{'s' if n != 1 else ''}"
                    + (
                        f" and {len(bridge_pairs)} first/last-frame transition bridge job"
                        f"{'s' if len(bridge_pairs) != 1 else ''}"
                        if bridge_pairs
                        else ""
                    )
                    + f" with concurrency {concurrency}."
                ),
                total=n,
            )
            while tasks:
                while not event_queue.empty():
                    event = await event_queue.get()
                    event.progress = completed / n * main_progress_end
                    yield event

                done, tasks = await asyncio.wait(tasks, timeout=0.25, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    i, clip = await task
                    completed += 1
                    if clip:
                        shots[i] = shots[i].model_copy(
                            update={
                                "video_clip_path": str(clip),
                                "trim_handle_sec": scene_handle_sec + motion_preroll_trim_sec,
                            }
                        )
                        message = f"Finished shot {completed} of {n}: {shots[i].slot_id.replace('_', ' ')}."
                    else:
                        log.warning("FAL failed for shot %s — will skip", shots[i].slot_id)
                        message = f"Shot {shots[i].slot_id.replace('_', ' ')} failed in FAL; continuing with available clips."
                    yield RenderProgress(
                        progress=completed / n * main_progress_end,
                        seconds_done=0.0,
                        fps=0.0,
                        phase="fal",
                        message=message,
                        current=completed,
                        total=n,
                        shot_id=shots[i].slot_id,
                    )

            yield RenderProgress(
                progress=main_progress_end,
                seconds_done=0.0,
                fps=0.0,
                phase="fal",
                message=(
                    "Shot clips are ready. Generating source-to-source transition bridges next."
                    if bridge_pairs
                    else "All available shot clips are ready."
                ),
                current=n,
                total=n,
            )

            if bridge_pairs:
                bridge_total = len(bridge_pairs)
                bridge_completed = 0
                bridge_span = 0.70 - main_progress_end

                async def generate_bridge(pair_number: int, shot_index: int):
                    async with semaphore:
                        start_shot = shots[shot_index]
                        end_shot = shots[shot_index + 1]
                        bridge_id = f"{start_shot.slot_id}_to_{end_shot.slot_id}"
                        await event_queue.put(
                            RenderProgress(
                                progress=main_progress_end,
                                seconds_done=0.0,
                                fps=0.0,
                                phase="fal_transition",
                                message=(
                                    f"Generating transition bridge {pair_number + 1} of {bridge_total}: "
                                    f"{start_shot.slot_id.replace('_', ' ')} to {end_shot.slot_id.replace('_', ' ')}."
                                ),
                                current=pair_number + 1,
                                total=bridge_total,
                                shot_id=bridge_id,
                            )
                        )
                        clip_path = scratch / (
                            f"bridge_{shot_index:02d}_"
                            f"{_safe_file_part(start_shot.slot_id)}_to_{_safe_file_part(end_shot.slot_id)}.mp4"
                        )
                        raw_clip_path = scratch / (
                            f"bridge_raw_{shot_index:02d}_"
                            f"{_safe_file_part(start_shot.slot_id)}_to_{_safe_file_part(end_shot.slot_id)}.mp4"
                        )
                        bridge_duration = _bridge_duration_sec(
                            start_shot,
                            end_shot,
                            default=transition_duration_sec,
                        )
                        bridge_generation_duration = max(3.0, bridge_duration)
                        out_w, out_h = config.output_resolution()
                        clip = await self.fal.first_last_frame_to_video(
                            start_image_path=Path(start_shot.image_path),
                            end_image_path=Path(end_shot.image_path),
                            prompt=_fal_transition_prompt(storyboard, start_shot, end_shot),
                            out_path=raw_clip_path,
                            duration_sec=bridge_generation_duration,
                        )
                        if not clip:
                            return shot_index, None, bridge_duration
                        cooked = await cook_transition_bridge(
                            input_path=clip,
                            output_path=clip_path,
                            start_image_path=Path(start_shot.image_path),
                            end_image_path=Path(end_shot.image_path),
                            duration_sec=bridge_duration,
                            raw_duration_sec=bridge_generation_duration,
                            movement_intensity=_movement_intensity(start_shot),
                            out_w=out_w,
                            out_h=out_h,
                            fps=config.fps,
                            ffmpeg_bin=self.builder.ffmpeg,
                        )
                        return shot_index, (cooked.output_path if cooked else clip), bridge_duration

                bridge_tasks = {
                    asyncio.create_task(generate_bridge(pair_number, shot_index))
                    for pair_number, shot_index in enumerate(bridge_pairs)
                }
                while bridge_tasks:
                    while not event_queue.empty():
                        event = await event_queue.get()
                        event.progress = main_progress_end + (bridge_completed / bridge_total) * bridge_span
                        yield event

                    done, bridge_tasks = await asyncio.wait(
                        bridge_tasks,
                        timeout=0.25,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        shot_index, clip, bridge_duration = await task
                        bridge_completed += 1
                        start_shot = shots[shot_index]
                        end_shot = shots[shot_index + 1]
                        if clip:
                            transition_bridge_clips[shot_index] = clip
                            transition_bridge_durations[shot_index] = bridge_duration
                            message = (
                                f"Finished transition bridge {bridge_completed} of {bridge_total}: "
                                f"{start_shot.slot_id.replace('_', ' ')} to {end_shot.slot_id.replace('_', ' ')}."
                            )
                        else:
                            message = (
                                f"Transition bridge {start_shot.slot_id.replace('_', ' ')} to "
                                f"{end_shot.slot_id.replace('_', ' ')} failed; using direct stitch instead."
                            )
                        yield RenderProgress(
                            progress=main_progress_end + (bridge_completed / bridge_total) * bridge_span,
                            seconds_done=0.0,
                            fps=0.0,
                            phase="fal_transition",
                            message=message,
                            current=bridge_completed,
                            total=bridge_total,
                            shot_id=f"{start_shot.slot_id}_to_{end_shot.slot_id}",
                        )

                yield RenderProgress(
                    progress=0.70,
                    seconds_done=0.0,
                    fps=0.0,
                    phase="fal_transition",
                    message=(
                        f"Transition bridges ready: {len(transition_bridge_clips)} of {bridge_total} generated."
                    ),
                    current=len(transition_bridge_clips),
                    total=bridge_total,
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
        assembly_shots = _shots_with_transition_bridges(
            shots,
            transition_bridge_clips,
            bridge_durations_sec=transition_bridge_durations,
            default_bridge_duration_sec=transition_duration_sec,
        )
        total_dur = (
            sum(s.duration_sec for s in assembly_shots if s.video_clip_path)
            or sum(s.duration_sec for s in shots)
        )
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
        clips_ready = [s for s in assembly_shots if s.video_clip_path]

        if clips_ready:
            cmd = self.builder.build_from_clips(
                shots=clips_ready,
                config=config,
                output_path=output_path,
                audio_cue_files=cue_files,
                total_duration_sec=sum(s.duration_sec for s in clips_ready),
                audio_cues=storyboard.audio_cues,
                beat_timestamps=storyboard.beat_timestamps or [],
                transition_sfx=_transition_sfx_events(
                    clips_ready,
                    beat_timestamps=storyboard.beat_timestamps or [],
                    fps=config.fps,
                ),
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


def _motion_lead(shot) -> str:
    strategy = _transition_strategy(shot)
    profile = str(getattr(shot, "ramp_profile", "") or "").lower()
    motion = str(getattr(getattr(shot, "motion", ""), "value", getattr(shot, "motion", "")) or "").lower()
    motion_text = " ".join(
        str(value or "")
        for value in [
            getattr(shot, "style_notes", ""),
            getattr(shot, "transition_plan", ""),
            getattr(shot, "velocity_vector", ""),
        ]
    ).lower()

    if strategy == "whip_pan":
        return "++Fast whip-pan camera move++"
    if strategy == "reveal" or profile == "reveal":
        return "++Dolly in fast, then slow down smoothly++"
    if profile == "impact":
        return "++Push in with a confident landing move++"
    if "whip" in motion_text:
        return "++Fast whip-pan camera move++"
    if "dolly" in motion_text or "push" in motion_text:
        return "++Dolly in with clear cinematic motion++"
    if "pull" in motion_text:
        return "++Pull back with smooth reveal motion++"
    if "pan left" in motion_text:
        return "++Pan left immediately, steady camera motion++"
    if "pan right" in motion_text:
        return "++Pan right immediately, steady camera motion++"
    if motion in {"push_in", "slow_zoom_in"}:
        return "++Dolly in with clear cinematic motion++"
    if motion in {"pull_out", "slow_zoom_out"}:
        return "++Pull back with smooth reveal motion++"
    if motion == "pan_left":
        return "++Pan left immediately, steady camera motion++"
    if motion == "pan_right":
        return "++Pan right immediately, steady camera motion++"
    if motion == "pan_up":
        return "++Tilt up immediately, smooth architectural reveal++"
    if motion == "pan_down":
        return "++Tilt down immediately, smooth architectural reveal++"
    return "++Smooth continuous camera glide++"


def _bridge_motion_lead(start_shot, end_shot) -> str:
    strategy = _transition_strategy(start_shot)
    if strategy == "whip_pan" or _movement_intensity(start_shot) == "fast":
        return "++Fast whip-pan bridge from @Image1 to @Image2++"
    if strategy == "reveal":
        return "++Speed-ramp reveal from @Image1 into @Image2++"
    if getattr(start_shot, "velocity_vector", None):
        return f"++Continue {start_shot.velocity_vector} from @Image1 into @Image2++"
    return "++Forward dolly bridge from @Image1 to @Image2++"


def _recipe_style_line(recipe) -> str:
    if not recipe:
        return "Cinematic 4k, premium architectural light, calm commercial luxury."
    bits = [
        getattr(recipe, "mood", ""),
        getattr(recipe, "camera_motion", ""),
        getattr(recipe, "environmental_dynamics", ""),
    ]
    return _short_prompt(" ".join(str(bit) for bit in bits if bit), 180) or "Cinematic 4k, premium architectural light."


def _short_prompt(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


def _fal_provider_prompt(storyboard: Storyboard, shot, recipe, prev_shot=None, next_shot=None) -> str:
    """Motion-first FAL prompt; long director notes stay in storyboard metadata."""
    brief = storyboard.creative_brief
    room = (getattr(shot, "room_type", None) or "property scene").replace("_", " ")
    motion_lead = _motion_lead(shot)
    continuity = _neighbor_transition_text(prev_shot, shot, next_shot)
    parts = [
        f"{motion_lead}. Immediate camera movement from frame 0; keep visible motion through the full clip.",
        f"High fidelity to @Image1/source photo. High-end {room} based on the uploaded image.",
        (
            f"Story: {brief.concept_title}. {brief.logline}"
            if brief and (brief.concept_title or brief.logline)
            else ""
        ),
        f"Scene purpose: {_short_prompt(shot.scene_purpose, 180)}" if shot.scene_purpose else "",
        (
            f"Inertia: start already moving; inherit {shot.velocity_vector}."
            if getattr(shot, "velocity_vector", None)
            else ""
        ),
        (
            f"User direction: {_short_prompt(shot.user_direction, 220)}"
            if getattr(shot, "user_direction", None)
            else ""
        ),
        f"Camera path: {_short_prompt(shot.style_notes or shot.transition_plan, 260)}"
        if (shot.style_notes or shot.transition_plan)
        else "",
        f"Edit handoff: {_short_prompt(continuity, 260)}" if continuity else "",
        f"Rhythm: {_short_prompt(shot.beat_plan, 180)}" if shot.beat_plan else "",
        f"Look: {_recipe_style_line(recipe)}",
        (
            f"Music feel: {_short_prompt(brief.music_strategy, 160)}"
            if brief and brief.music_strategy
            else "Music: calm commercial dramatic pacing; cuts breathe on downbeats."
        ),
        "Temporal progression: this must read as video, not a still photo.",
    ]
    return _compact_prompt(parts, max_chars=1050)


def _fal_transition_prompt(storyboard: Storyboard, start_shot, end_shot) -> str:
    """Motion-first first/last-frame bridge prompt."""
    brief = storyboard.creative_brief
    motion_lead = _bridge_motion_lead(start_shot, end_shot)
    parts = [
        f"{motion_lead}. Immediate camera movement from frame 0; do not settle or hold.",
        "First/last-frame transition: begin at @Image1 and arrive at @Image2 with continuous visible motion.",
        "High fidelity to both source frames; keep the edit fluid, not frozen.",
        (
            f"Story: {brief.concept_title}. {brief.logline}"
            if brief and (brief.concept_title or brief.logline)
            else ""
        ),
        f"Start scene: {_shot_context_line(start_shot)}.",
        f"End scene: {_shot_context_line(end_shot)}.",
        (
            f"User direction: {_short_prompt(start_shot.user_direction, 180)}"
            if getattr(start_shot, "user_direction", None)
            else ""
        ),
        f"Egress: {_short_prompt(start_shot.egress_seam, 180)}" if start_shot.egress_seam else "",
        f"Ingress: {_short_prompt(end_shot.ingress_seam, 180)}" if end_shot.ingress_seam else "",
        f"Velocity: {_short_prompt(end_shot.velocity_vector, 120)}" if end_shot.velocity_vector else "",
        (
            "Shared anchor: "
            f"{', '.join(start_shot.shared_anchors_to_next)}"
            if getattr(start_shot, "shared_anchors_to_next", None)
            else ""
        ),
        f"Bridge move: {_short_prompt(start_shot.bridge_instructions, 240)}" if start_shot.bridge_instructions else "",
        f"Director edit: {_transition_strategy(start_shot)}; {_short_prompt(_transition_logic_text(start_shot), 180)}",
        (
            f"Visual distance {start_shot.visual_distance_score:.1f}/10; movement {_movement_intensity(start_shot)}."
            if start_shot.visual_distance_score is not None
            else f"Movement {_movement_intensity(start_shot)}."
        ),
        "If the spatial path feels risky, use a fast whip-like camera blur through the seam rather than a slow morph.",
    ]
    return _compact_prompt(parts, max_chars=950)


def _neighbor_transition_text(prev_shot, shot, next_shot) -> str:
    """Describe how this one-image clip should connect to adjacent storyboard clips."""
    parts: list[str] = []
    if prev_shot:
        prev_vector = _short_prompt(getattr(prev_shot, "egress_seam", "") or getattr(prev_shot, "velocity_vector", ""), 140)
        parts.append(f"Continue previous camera energy{f': {prev_vector}' if prev_vector else ''}.")
    if next_shot:
        strategy = _transition_strategy(shot)
        fallback = "cut exactly on the beat."
        if strategy in {"whip_pan", "whip_pan_blur"}:
            fallback = "exit with a fast directional whip and cut on the beat."
        elif strategy == "reveal":
            fallback = "push toward the reveal target and cut on the beat."
        elif strategy == "match_cut":
            fallback = "end on the matching shape or axis and cut on the beat."
        next_room = (getattr(next_shot, "room_type", None) or "next scene").replace("_", " ")
        parts.append(f"Set up {next_room}: {fallback}")
    if not parts:
        return ""
    return " ".join(parts)


def _shot_context_line(shot) -> str:
    room = (getattr(shot, "room_type", None) or "property scene").replace("_", " ")
    purpose = " ".join(str(getattr(shot, "scene_purpose", "") or "").split())
    transition = " ".join(str(getattr(shot, "transition_plan", "") or "").split())
    context = purpose or transition or getattr(shot, "slot_id", room)
    return _compact_prompt([f"{getattr(shot, 'slot_id', room)} / {room}: {context}"], max_chars=260)


def _transition_bridge_pairs(shots: list) -> list[int]:
    return [
        index
        for index in range(len(shots) - 1)
        if _source_image_exists(shots[index])
        and _source_image_exists(shots[index + 1])
        and _should_generate_flfv_bridge(shots[index], shots[index + 1])
    ]


def _source_image_exists(shot) -> bool:
    image_path = getattr(shot, "image_path", None)
    return bool(image_path) and Path(image_path).exists()


def _transition_strategy(shot) -> str:
    logic = getattr(shot, "transition_logic", None)
    if isinstance(logic, dict):
        strategy = _normalize_transition_strategy(logic.get("strategy"))
        if strategy:
            return "whip_pan" if strategy == "handshake" and _handshake_static_risk(shot) else strategy
    strategy = _normalize_transition_strategy(getattr(shot, "bridge_strategy", None)) or "simple_cut"
    return "whip_pan" if strategy == "handshake" and _handshake_static_risk(shot) else strategy


def _normalize_transition_strategy(value) -> str:
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


def _transition_logic_text(shot) -> str:
    logic = getattr(shot, "transition_logic", None)
    if not isinstance(logic, dict):
        return ""
    parts = [
        f"strategy {_transition_strategy(shot)}",
        f"execution {logic.get('technical_execution')}" if logic.get("technical_execution") else "",
        f"spatial continuity {logic.get('spatial_continuity')}" if logic.get("spatial_continuity") else "",
        str(logic.get("justification") or ""),
        str(logic.get("risk_notes") or ""),
    ]
    return _compact_prompt([part for part in parts if part], max_chars=620)


def _handshake_static_risk(shot) -> bool:
    enabled = os.getenv("FAL_STATIC_HANDSHAKE_FALLBACK", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled or getattr(shot, "is_transition_bridge", False):
        return False
    intensity = str(getattr(shot, "movement_intensity", "") or "").lower()
    motion = str(getattr(getattr(shot, "motion", ""), "value", getattr(shot, "motion", "")) or "").lower()
    if intensity not in {"", "calm"} or motion not in {"", "static"}:
        return False

    movement_text = " ".join(
        str(value or "")
        for value in [
            getattr(shot, "velocity_vector", ""),
            getattr(shot, "egress_seam", ""),
            getattr(shot, "bridge_instructions", ""),
            getattr(shot, "transition_plan", ""),
            getattr(shot, "style_notes", ""),
        ]
    ).lower()
    motion_verbs = {
        "dolly",
        "push",
        "pull",
        "pan",
        "tilt",
        "truck",
        "orbit",
        "glide",
        "move",
        "rush",
        "whip",
        "speed",
        "drift",
        "crane",
    }
    return not any(verb in movement_text for verb in motion_verbs)


def _snap_shots_to_audio_grid(shots: list, beat_timestamps: list[float]) -> list:
    if len(shots) < 2 or len(beat_timestamps) < 2:
        return shots

    grid = sorted(float(t) for t in beat_timestamps if float(t) >= 0)
    if not grid:
        return shots

    total_duration = sum(max(0.1, float(shot.duration_sec)) for shot in shots)
    boundaries = [0.0]
    cursor = 0.0
    for shot in shots[:-1]:
        cursor += max(0.1, float(shot.duration_sec))
        boundaries.append(cursor)
    boundaries.append(total_duration)

    snapped = [0.0]
    min_scene = _snappy_min_scene_sec()
    for index, boundary in enumerate(boundaries[1:-1], start=1):
        remaining = len(shots) - index
        lower = snapped[-1] + min_scene
        upper = total_duration - remaining * min_scene
        candidate = _nearest_grid_time(grid, boundary, lower=lower, upper=upper)
        if candidate is None or abs(candidate - boundary) > 1.1:
            candidate = max(lower, min(upper, boundary))
        snapped.append(candidate)
    snapped.append(total_duration)

    out = []
    for index, shot in enumerate(shots):
        start = snapped[index]
        end = snapped[index + 1]
        out.append(
            shot.model_copy(
                update={
                    "start_time_sec": start,
                    "duration_sec": max(0.5, end - start),
                }
            )
        )
    return out


def _nearest_grid_time(grid: list[float], target: float, lower: float, upper: float) -> Optional[float]:
    candidates = [time for time in grid if lower <= time <= upper]
    if not candidates:
        return None
    return min(candidates, key=lambda time: abs(time - target))


def _scene_handle_sec() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("FAL_SCENE_HANDLE_SEC", "0.5"))))
    except ValueError:
        return 0.5


def _snappy_min_scene_sec() -> float:
    try:
        return max(0.75, min(3.0, float(os.getenv("SNAPPY_MIN_SHOT_SEC", "1.35"))))
    except ValueError:
        return 1.35


def _motion_preroll_trim_sec() -> float:
    try:
        return max(0.0, min(0.5, float(os.getenv("FAL_MOTION_PREROLL_TRIM_SEC", "0.2"))))
    except ValueError:
        return 0.2


def _should_generate_flfv_bridge(start_shot, end_shot) -> bool:
    strategy = _transition_strategy(start_shot)
    if strategy in {"reveal", "whip_pan", "simple_cut", "match_cut", "skip", "cut", "dissolve", "whip_pan_blur", "none"}:
        return False
    if strategy not in {"handshake", "flfv_bridge"}:
        return False

    distance = getattr(start_shot, "visual_distance_score", None)
    anchors = getattr(start_shot, "shared_anchors_to_next", None) or []
    if distance is not None and distance > 6.0 and not anchors:
        return False

    start_room = getattr(start_shot, "room_type", None)
    end_room = getattr(end_shot, "room_type", None)
    if distance is None and start_room and end_room and start_room != end_room:
        return bool(anchors)
    return True


def _bridge_duration_sec(start_shot, end_shot, default: float) -> float:
    if getattr(start_shot, "bridge_duration_sec", None):
        return max(1.5, min(4.0, float(start_shot.bridge_duration_sec)))
    distance = getattr(start_shot, "visual_distance_score", None)
    if distance is None:
        start_room = getattr(start_shot, "room_type", None)
        end_room = getattr(end_shot, "room_type", None)
        distance = 3.0 if start_room and end_room and start_room == end_room else 6.0
    if distance <= 3:
        return 1.5
    if distance >= 8:
        return 4.0
    return max(2.25, min(3.25, default))


def _movement_intensity(shot) -> str:
    value = str(getattr(shot, "movement_intensity", "") or "").lower()
    if value in {"calm", "moderate", "fast"}:
        return value
    strategy = _transition_strategy(shot)
    if strategy in {"whip_pan", "whip_pan_blur"}:
        return "fast"
    if strategy in {"reveal", "match_cut"}:
        return "moderate"
    distance = getattr(shot, "visual_distance_score", None)
    if distance is not None and distance >= 8:
        return "moderate"
    return "calm"


def _shots_with_transition_bridges(
    shots: list,
    bridge_clips: dict[int, Path],
    bridge_durations_sec: dict[int, float],
    default_bridge_duration_sec: float,
) -> list:
    if not bridge_clips:
        return shots

    assembly: list = []
    for index, shot in enumerate(shots):
        bridge_in_duration = bridge_durations_sec.get(index - 1, default_bridge_duration_sec)
        bridge_out_duration = bridge_durations_sec.get(index, default_bridge_duration_sec)
        bridge_in = bridge_in_duration / 2 if index - 1 in bridge_clips else 0.0
        bridge_out = bridge_out_duration / 2 if index in bridge_clips else 0.0
        main_duration = max(1.5, shot.duration_sec - bridge_in - bridge_out)
        assembly.append(shot.model_copy(update={"duration_sec": main_duration}))

        bridge_clip = bridge_clips.get(index)
        if not bridge_clip or index + 1 >= len(shots):
            continue

        next_shot = shots[index + 1]
        bridge_duration_sec = bridge_durations_sec.get(index, default_bridge_duration_sec)
        assembly.append(
            shot.model_copy(
                update={
                    "slot_id": f"{shot.slot_id}_to_{next_shot.slot_id}",
                    "duration_sec": bridge_duration_sec,
                    "video_clip_path": str(bridge_clip),
                    "is_transition_bridge": True,
                    "text_overlay_id": None,
                    "rendered_text_overlay": None,
                    "scene_purpose": f"True first/last-frame transition from {shot.slot_id} to {next_shot.slot_id}.",
                    "style_notes": None,
                    "beat_plan": None,
                    "masking_plan": None,
                    "transition_plan": None,
                    "continuity_notes": None,
                    "rubric_plan": None,
                    "style_recipe_prompt": None,
                    "user_direction": None,
                }
            )
        )
    return assembly


def _transition_sfx_events(shots: list, beat_timestamps: list[float], fps: int) -> list[TransitionSfxEvent]:
    events: list[TransitionSfxEvent] = []
    cursor = 0.0
    for index, shot in enumerate(shots):
        duration = _timeline_quantized_sec(getattr(shot, "duration_sec", 0.0) or 0.0, fps)
        if getattr(shot, "is_transition_bridge", False):
            intensity = _movement_intensity(shot)
            sfx_duration = min(1.6, max(0.8, duration * 0.72))
            bridge_peak = cursor + duration * 0.5
            bridge_peak = _nearest_sfx_peak(bridge_peak, beat_timestamps)
            events.append(
                TransitionSfxEvent(
                    start_sec=max(0.0, bridge_peak - sfx_duration * 0.5),
                    duration_sec=sfx_duration,
                    intensity=intensity,
                    add_impact=intensity in {"moderate", "fast"},
                )
            )
        elif index + 1 < len(shots) and not getattr(shots[index + 1], "is_transition_bridge", False):
            strategy = _transition_strategy(shot)
            if strategy in {"whip_pan", "reveal", "match_cut"}:
                if strategy == "whip_pan":
                    sfx_duration = 1.05
                    intensity = "fast"
                    add_impact = True
                elif strategy == "reveal":
                    sfx_duration = 0.85
                    intensity = "moderate"
                    add_impact = True
                else:
                    sfx_duration = 0.55
                    intensity = "calm"
                    add_impact = False
                peak = _nearest_sfx_peak(cursor + duration, beat_timestamps)
                events.append(
                    TransitionSfxEvent(
                        start_sec=max(0.0, peak - sfx_duration * 0.72),
                        duration_sec=sfx_duration,
                        intensity=intensity,
                        add_impact=add_impact,
                    )
                )
        cursor += duration
    return events


def _timeline_quantized_sec(value, fps: int) -> float:
    try:
        seconds = max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0
    frame = 1.0 / max(fps, 1)
    return max(0.0, round(seconds / frame) * frame)


def _nearest_sfx_peak(target: float, beat_timestamps: list[float]) -> float:
    if not beat_timestamps:
        return target
    candidates = [float(time) for time in beat_timestamps if abs(float(time) - target) <= 0.25]
    if not candidates:
        return target
    return min(candidates, key=lambda time: abs(time - target))


def _safe_file_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return cleaned[:80] or "shot"


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
