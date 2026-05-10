"""High-level service: build storyboards from uploaded images."""
from __future__ import annotations

import logging
import asyncio
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from .agents.image_analyzer import ImageAnalyzer, ImageAnalysisResult
from .agents.photo_selector import PhotoSelector
from .agents.prompt_standard import FAL_SHOT_SOP
from .agents.shot_matcher import AnalyzedUpload, ShotMatcher
from .data.style_recipes import get_cinematic_for_room
from .models.project import Project
from .models.storyboard import ResolvedShot, Storyboard, StoryboardCreativeBrief, StoryboardMusic
from .models.template import Template
from .schedulers.pacing import PacingScheduler
from .storage.filesystem import ProjectFiles

log = logging.getLogger(__name__)

_CLIP_DURATION_SEC = 5.0  # fixed until beat-analysis module is wired in
TelemetryCallback = Callable[[dict[str, Any]], Awaitable[None]]


class StoryboardBuilder:
    def __init__(
        self,
        analyzer: Optional[ImageAnalyzer] = None,
        selector: Optional[PhotoSelector] = None,
        matcher: Optional[ShotMatcher] = None,
        scheduler: Optional[PacingScheduler] = None,
        project_files: Optional[ProjectFiles] = None,
    ):
        self.analyzer = analyzer or ImageAnalyzer()
        self.selector = selector or PhotoSelector()
        self.matcher = matcher or ShotMatcher()
        self.scheduler = scheduler or PacingScheduler()
        self.project_files = project_files or ProjectFiles()
        self.last_analyses_by_upload_id: dict[str, ImageAnalysisResult] = {}

    async def build(
        self,
        project: Project,
        template: Template,
        uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]],
        audio_path_for_pacing: Optional[Path] = None,
        beat_timestamps_ms: Optional[list[int]] = None,
        music: Optional[StoryboardMusic] = None,
        telemetry: Optional[TelemetryCallback] = None,
    ) -> Storyboard:
        # 1. Analyze any unanalyzed uploads concurrently, then cache them in the API layer.
        await _emit(
            telemetry,
            stage="storyboard",
            message=f"Analyzing {len(uploads)} photo{'s' if len(uploads) != 1 else ''} for room type, quality, framing, and cinematic use.",
            progress=0.08,
        )
        analyzed = await self._analyze_uploads(uploads, telemetry=telemetry)

        music_context = _music_context(music, beat_timestamps_ms)
        await _emit(
            telemetry,
            stage="storyboard",
            message=f"Curating {len(analyzed)} analyzed photo{'s' if len(analyzed) != 1 else ''} against the scene rubric.",
            progress=0.56,
        )
        selection = await self.selector.select(
            project=project,
            template=template,
            uploads=analyzed,
            music_context=music_context,
        )
        selected_ids = [upload_id for upload_id in selection.selected_upload_ids if upload_id]
        analyzed_by_id = {upload.upload_id: upload for upload in analyzed}
        curated_analyzed = [analyzed_by_id[upload_id] for upload_id in selected_ids if upload_id in analyzed_by_id]
        if not curated_analyzed:
            curated_analyzed = analyzed
            selected_ids = [upload.upload_id for upload in analyzed]
        curation_context = " ".join(
            part
            for part in [
                music_context,
                f"Photo curation concept hint: {selection.concept_hint}." if selection.concept_hint else "",
                f"Photo curation notes: {selection.notes}." if selection.notes else "",
            ]
            if part
        )
        await _emit(
            telemetry,
            stage="storyboard",
            message=(
                f"Selected {len(curated_analyzed)} of {len(analyzed)} photo"
                f"{'s' if len(analyzed) != 1 else ''} for the strongest story arc."
            ),
            progress=0.62,
            detail={
                "selected_upload_ids": selected_ids,
                "rejected_upload_ids": selection.rejected_upload_ids,
            },
        )

        # 2. Match curated images to slots. Storyboard generation only plans; render generates FAL clips later.
        await _emit(
            telemetry,
            stage="storyboard",
            message="Planning story order, shot assignments, camera motion, and beat-aware pacing.",
            progress=0.68,
        )
        match = await self.matcher.match(template, curated_analyzed, music_context=curation_context)
        creative_brief = _creative_brief_model(
            match.creative_brief,
            template=template,
            upload_count=len(curated_analyzed),
            music_context=curation_context,
        )

        # 3. Build shots with style recipes. With any real uploads present, reuse real photos
        # instead of spawning generated filler rooms.
        upload_by_id = {u.upload_id: u for u in curated_analyzed}
        slot_by_id = template.slot_by_id
        ordered_slots = [slot_by_id[slot_id] for slot_id in match.slot_order if slot_id in slot_by_id]
        ordered_slots.extend(slot for slot in template.shot_slots if slot.slot_id not in {s.slot_id for s in ordered_slots})
        ordered_slots = _adapt_slots_to_upload_count(ordered_slots, len(curated_analyzed))
        await _emit(
            telemetry,
            stage="storyboard",
            message=f"Writing cinematic style recipes for {len(ordered_slots)} planned shots.",
            progress=0.78,
        )

        ordered_template = template.model_copy(update={"shot_slots": ordered_slots})
        timings = self.scheduler.schedule(
            ordered_template,
            str(audio_path_for_pacing) if audio_path_for_pacing else None,
            beat_timestamps_ms=beat_timestamps_ms,
        )
        timing_by_slot = {t.slot_id: t for t in timings}
        overlay_by_id = template.text_overlay_by_id

        shots: list[ResolvedShot] = []
        cursor = 0.0
        for index, slot in enumerate(ordered_slots):
            assigned_id = match.assignments.get(slot.slot_id)
            upload_analysis: Optional[ImageAnalysisResult] = None

            if assigned_id and assigned_id in upload_by_id:
                image_path = upload_by_id[assigned_id].image_path
                upload_analysis = upload_by_id[assigned_id].analysis
                room_type = upload_analysis.room_type or slot.room_type
                is_generated = False
                source_upload_id = assigned_id
            elif slot.must_fill and slot.fallback_to_generated:
                # No matching upload: leave image_path empty so render uses FAL text-to-video.
                image_path = ""
                room_type = slot.room_type
                is_generated = True
                source_upload_id = None
            else:
                continue  # optional slot, drop it

            timing = timing_by_slot.get(slot.slot_id)
            duration_sec = _clip_duration(timing.duration_sec if timing else slot.duration_sec)
            override = match.style_overrides.get(slot.slot_id, {})
            scene_purpose = str(override.get("scene_purpose") or "").strip()
            beat_plan = str(override.get("beat_plan") or "").strip()
            masking_plan = str(override.get("masking_plan") or "").strip()
            transition_plan = str(override.get("transition_plan") or "").strip()
            continuity_notes = str(override.get("continuity_notes") or "").strip()
            style_notes = str(override.get("style_notes") or "").strip()
            rubric_plan = _clean_rubric_plan(override.get("rubric_plan") or override.get("rubric"))
            recipe_intent = " ".join(
                part
                for part in [
                    slot.description,
                    room_type or "",
                    scene_purpose,
                    style_notes,
                    transition_plan,
                    _rubric_text(rubric_plan),
                    creative_brief.visual_theme,
                ]
                if part
            )
            recipe = get_cinematic_for_room(room_type, seed=index, intent=recipe_intent)
            if upload_analysis and slot.room_type and upload_analysis.room_type != slot.room_type:
                style_notes = (
                    f"{style_notes} The source upload is analyzed as {upload_analysis.room_type}, "
                    f"not {slot.room_type}; preserve the real source image and treat this as a grounded "
                    "bridge shot instead of inventing a missing room."
                ).strip()
                continuity_notes = (
                    f"{continuity_notes} This is a grounded repurposed scene: do not change the room identity "
                    f"from {upload_analysis.room_type} into {slot.room_type}."
                ).strip()
            style_recipe_prompt = _style_recipe_prompt(
                project=project,
                slot_description=slot.description,
                room_type=room_type,
                recipe=recipe,
                creative_brief=creative_brief,
                scene_purpose=scene_purpose,
                style_notes=style_notes,
                beat_plan=beat_plan,
                masking_plan=masking_plan,
                transition_plan=transition_plan,
                continuity_notes=continuity_notes,
                rubric_plan=rubric_plan,
                music_context=music_context,
                has_source_image=bool(image_path),
            )
            rendered_text = None
            if slot.text_overlay_id and slot.text_overlay_id in overlay_by_id:
                rendered_text = _render_text_overlay(overlay_by_id[slot.text_overlay_id].text_template, project)

            shots.append(
                ResolvedShot(
                    slot_id=slot.slot_id,
                    image_path=image_path,
                    start_time_sec=cursor,
                    duration_sec=duration_sec,
                    motion=override.get("motion", slot.motion),
                    motion_strength=override.get("motion_strength", slot.motion_strength),
                    transition_in=override.get("transition_in", slot.transition_in),
                    color_grade=override.get("color_grade", slot.color_grade),
                    text_overlay_id=slot.text_overlay_id,
                    rendered_text_overlay=rendered_text,
                    is_generated=is_generated,
                    source_upload_id=source_upload_id,
                    room_type=room_type,
                    style_recipe_id=recipe.style_id if recipe else None,
                    style_notes=style_notes or None,
                    scene_purpose=scene_purpose or None,
                    beat_plan=beat_plan or None,
                    masking_plan=masking_plan or None,
                    transition_plan=transition_plan or None,
                    continuity_notes=continuity_notes or None,
                    rubric_plan=rubric_plan or None,
                    style_recipe_prompt=style_recipe_prompt,
                )
            )
            cursor += duration_sec

        total = cursor or template.target_duration_sec
        await _emit(
            telemetry,
            stage="storyboard",
            message=f"Storyboard ready: {len(shots)} shots, {len([s for s in shots if s.is_generated])} generated fallbacks, {total:.1f}s total.",
            status="succeeded",
            progress=1.0,
        )

        return Storyboard(
            storyboard_id=str(uuid.uuid4()),
            project_id=project.id,
            template_id=template.template_id,
            shots=shots,
            audio_cues=template.audio_cues,
            text_overlays=template.text_overlays,
            music=music,
            creative_brief=creative_brief,
            total_duration_sec=total,
            aspect_ratio=template.aspect_ratio,
            beat_timestamps=[ms / 1000 for ms in (beat_timestamps_ms or [])],
            generated_slot_ids=[s.slot_id for s in shots if s.is_generated],
            unfilled_slot_ids=list(match.unfilled),
            selected_upload_ids=selected_ids,
            rejected_upload_ids=selection.rejected_upload_ids,
            photo_selection_notes=selection.notes,
            notes=" ".join(part for part in [match.notes, selection.notes] if part).strip(),
        )

    async def _analyze_uploads(
        self,
        uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]],
        telemetry: Optional[TelemetryCallback] = None,
    ) -> list[AnalyzedUpload]:
        self.last_analyses_by_upload_id = {}
        semaphore = asyncio.Semaphore(4)
        completed = 0
        total = len(uploads)
        lock = asyncio.Lock()

        async def analyze_one(item: tuple[str, Path, Optional[ImageAnalysisResult]]) -> AnalyzedUpload:
            nonlocal completed
            upload_id, path, cached = item
            if cached is None:
                async with semaphore:
                    cached = await self.analyzer.analyze(path)
            self.last_analyses_by_upload_id[upload_id] = cached
            async with lock:
                completed += 1
                await _emit(
                    telemetry,
                    stage="storyboard",
                    message=(
                        f"Analyzed photo {completed} of {total}: "
                        f"{cached.room_type.replace('_', ' ')}, {cached.framing}, quality {cached.quality_score:.2f}."
                    ),
                    progress=0.10 + 0.45 * (completed / max(total, 1)),
                    detail={
                        "current": completed,
                        "total": total,
                        "upload_id": upload_id,
                        "room_type": cached.room_type,
                    },
                )
            return AnalyzedUpload(upload_id=upload_id, image_path=str(path), analysis=cached)

        return list(await asyncio.gather(*(analyze_one(upload) for upload in uploads)))


def _creative_brief_model(
    brief: dict[str, Any],
    *,
    template: Template,
    upload_count: int,
    music_context: str,
) -> StoryboardCreativeBrief:
    continuity = brief.get("continuity_rules") if isinstance(brief, dict) else []
    if not isinstance(continuity, list):
        continuity = [continuity]
    fallback_music = (
        music_context
        or "Use calm commercial pacing; let scene changes breathe and avoid aggressive music-video edits."
    )
    sparse_rule = (
        "Sparse upload mode: build the film from real available photos and reuse them with distinct scene intent."
        if upload_count and upload_count < 5
        else "Use actual uploads as the source of truth for room order and visual continuity."
    )
    return StoryboardCreativeBrief(
        concept_title=_clean_prompt_text(brief.get("concept_title") if isinstance(brief, dict) else "", 180)
        or f"{template.name}: cinematic property story",
        logline=_clean_prompt_text(brief.get("logline") if isinstance(brief, dict) else "", 500)
        or "A calm commercial reel that turns the available listing photos into one coherent property story.",
        visual_theme=_clean_prompt_text(brief.get("visual_theme") if isinstance(brief, dict) else "", 900)
        or "Smooth architectural motion, refined warm light, stable geometry, soft parallax, and clean editorial transitions.",
        emotional_arc=_clean_prompt_text(brief.get("emotional_arc") if isinstance(brief, dict) else "", 900)
        or "Orientation, invitation, material proof, emotional breath, and a polished closing memory.",
        music_strategy=_clean_prompt_text(brief.get("music_strategy") if isinstance(brief, dict) else "", 900)
        or fallback_music,
        continuity_rules=[
            *[_clean_prompt_text(item, 300) for item in continuity if _clean_prompt_text(item, 300)],
            "Preserve source-image architecture, layout, materials, and room identity.",
            sparse_rule,
        ][:8],
    )


def _adapt_slots_to_upload_count(slots: list, upload_count: int) -> list:
    if upload_count <= 0 or upload_count >= 5 or len(slots) <= 3:
        return slots
    target = min(len(slots), max(3, upload_count * 2))
    if target >= len(slots):
        return slots

    step = (len(slots) - 1) / (target - 1)
    indexes = sorted({round(i * step) for i in range(target)})
    while len(indexes) < target:
        for i in range(len(slots)):
            if i not in indexes:
                indexes.append(i)
                indexes.sort()
                break
    return [slots[i] for i in indexes[:target]]


def _clip_duration(duration_sec: float) -> float:
    return max(2.5, min(float(duration_sec), _CLIP_DURATION_SEC))


def _clean_prompt_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def _clean_rubric_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        clean_key = _clean_prompt_text(key, 80)
        if not clean_key:
            continue
        if isinstance(item, dict):
            nested = {
                _clean_prompt_text(nested_key, 80): _clean_prompt_text(nested_value, 700)
                for nested_key, nested_value in item.items()
                if _clean_prompt_text(nested_key, 80)
            }
            if nested:
                cleaned[clean_key] = nested
        else:
            cleaned[clean_key] = _clean_prompt_text(item, 2200 if clean_key == "FAL_GENERATION_PROMPT" else 900)
    return cleaned


def _rubric_text(value: dict[str, Any]) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for key, item in value.items():
        if isinstance(item, dict):
            nested = "; ".join(f"{nested_key}: {nested_value}" for nested_key, nested_value in item.items())
            parts.append(f"{key}: {nested}")
        else:
            parts.append(f"{key}: {item}")
    return " ".join(parts)


async def _emit(
    telemetry: Optional[TelemetryCallback],
    *,
    stage: str,
    message: str,
    status: str = "running",
    progress: Optional[float] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    if not telemetry:
        return
    payload: dict[str, Any] = {"stage": stage, "status": status, "message": message}
    if progress is not None:
        payload["progress"] = max(0.0, min(1.0, progress))
    if detail:
        payload.update(detail)
    await telemetry(payload)


def _music_context(music: Optional[StoryboardMusic], beat_timestamps_ms: Optional[list[int]]) -> str:
    if not music:
        return ""
    beat_count = len(beat_timestamps_ms or music.beat_timestamps_ms)
    return (
        f"Selected music: {music.artist} - {music.title}. "
        f"Tempo: {music.tempo or 'unknown'} BPM. Stored beat timestamps: {beat_count}. "
        "Use the audio to support dramatic but calm commercial cuts."
    )


def _style_recipe_prompt(
    project: Project,
    slot_description: str,
    room_type: Optional[str],
    recipe,
    creative_brief: StoryboardCreativeBrief,
    scene_purpose: str,
    style_notes: str,
    beat_plan: str,
    masking_plan: str,
    transition_plan: str,
    continuity_notes: str,
    rubric_plan: dict[str, Any],
    music_context: str,
    has_source_image: bool,
) -> str:
    property_bits = [project.name, project.address, project.description]
    property_context = ". ".join(bit for bit in property_bits if bit)
    recipe_bits = []
    if recipe:
        recipe_bits = [
            f"Style recipe {recipe.style_id}: {recipe.category}.",
            f"Mood: {recipe.mood}.",
            f"Camera motion: {recipe.camera_motion}.",
            f"Environmental dynamics: {recipe.environmental_dynamics}.",
            f"Recipe direction: {recipe.video_prompt}",
        ]

    grounding = (
        "Use the provided source image as the absolute visual truth: preserve the real architecture, "
        "layout, room identity, materials, window placement, furniture, landscaping, and color palette. "
        "Do not create new rooms, extra floors, impossible geometry, signage, text, people, logos, "
        "watermarks, or distorted fixtures."
        if has_source_image
        else
        "No source photo is available for this slot, so generate only a restrained real-estate bridge "
        "shot that matches the property context. Avoid impossible architecture and avoid adding text."
    )
    continuity_rules = " ".join(
        f"Continuity rule: {rule}." for rule in creative_brief.continuity_rules if rule
    )

    return " ".join(
        part
        for part in [
            FAL_SHOT_SOP,
            "Premium cinematic real-estate reel shot.",
            f"Binding concept: {creative_brief.concept_title}. {creative_brief.logline}",
            f"Whole-reel visual theme: {creative_brief.visual_theme}",
            f"Whole-reel emotional arc: {creative_brief.emotional_arc}",
            f"Storyboard need: {slot_description}.",
            f"Scene purpose: {scene_purpose}." if scene_purpose else "",
            f"Grounded room/visual anchor: {room_type or 'property detail'}.",
            f"Property context: {property_context}." if property_context else "",
            *recipe_bits,
            f"Editor-agent direction: {style_notes}" if style_notes else "",
            f"Beat plan: {beat_plan}" if beat_plan else "",
            f"Masking and holdout plan: {masking_plan}" if masking_plan else "",
            f"Transition plan: {transition_plan}" if transition_plan else "",
            f"Continuity notes: {continuity_notes}" if continuity_notes else "",
            f"Rubric scene plan: {_rubric_text(rubric_plan)}" if rubric_plan else "",
            continuity_rules,
            f"Music strategy: {creative_brief.music_strategy}" if creative_brief.music_strategy else "",
            f"Audio/editing context: {music_context}" if music_context else "",
            grounding,
            "Make the motion smooth, expensive, calm, dramatic, and commercial. Favor controlled dolly, "
            "slider, crane, parallax, soft light movement, natural reflections, subtle atmosphere, and "
            "clean editorial timing over hype, whip-heavy, trap-style, or chaotic movement.",
        ]
        if part
    )


def _render_text_overlay(template: str, project: Project) -> Optional[str]:
    values = {
        "address": project.address or "",
        "price": project.price or "",
        "beds": "" if project.beds is None else str(project.beds),
        "baths": "" if project.baths is None else str(project.baths),
        "sqft": "" if project.sqft is None else str(project.sqft),
        "name": project.name or "",
        "description": project.description or "",
    }
    has_property_placeholder = "property." in template
    has_value_for_placeholder = any(
        value and f"property.{key}" in template
        for key, value in values.items()
    )
    if has_property_placeholder and not has_value_for_placeholder:
        return None

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{ property.{key} }}}}", value)
        rendered = rendered.replace(f"{{{{property.{key}}}}}", value)
    rendered = "\n".join(line.strip() for line in rendered.splitlines()).strip()
    return rendered or None


def _fallback_generation_prompt(project: Project, slot_description: str, style_notes: str = "") -> str:
    property_bits = [
        project.name,
        project.address,
        project.description,
    ]
    property_context = ". ".join(bit for bit in property_bits if bit)
    context_line = f"Property context: {property_context}." if property_context else ""
    style_line = f"Editor camera/style notes: {style_notes}." if style_notes else ""
    return (
        f"{FAL_SHOT_SOP} "
        "Generate a realistic high-end real-estate listing image for a vertical cinematic reel. "
        "Use the uploaded reference photos as visual anchors for architecture, materials, lighting, "
        "and property identity when provided. Do not add text, logos, watermarks, distorted rooms, "
        "or impossible architecture. Keep it polished, commercial, dramatic, and soothing. "
        f"Needed shot: {slot_description}. {context_line} {style_line}"
    ).strip()
