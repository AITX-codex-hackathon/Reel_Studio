"""High-level service: build storyboards from uploaded images."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from .agents.image_analyzer import ImageAnalyzer, ImageAnalysisResult
from .agents.shot_matcher import AnalyzedUpload, ShotMatcher
from .data.style_recipes import ROOM_ORDER, get_for_room
from .models.project import Project
from .models.storyboard import ResolvedShot, Storyboard, StoryboardMusic
from .models.template import Template
from .schedulers.pacing import PacingScheduler
from .storage.filesystem import ProjectFiles

log = logging.getLogger(__name__)

_CLIP_DURATION_SEC = 5.0  # fixed until beat-analysis module is wired in


class StoryboardBuilder:
    def __init__(
        self,
        analyzer: Optional[ImageAnalyzer] = None,
        matcher: Optional[ShotMatcher] = None,
        scheduler: Optional[PacingScheduler] = None,
        nano_banana: Optional[NanoBananaClient] = None,
        project_files: Optional[ProjectFiles] = None,
    ):
        self.analyzer = analyzer or ImageAnalyzer()
        self.matcher = matcher or ShotMatcher()
        self.scheduler = scheduler or PacingScheduler()
        self.nano_banana = nano_banana or NanoBananaClient()
        self.project_files = project_files or ProjectFiles()

    async def build(
        self,
        project: Project,
        template: Template,
        uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]],
        audio_path_for_pacing: Optional[Path] = None,
        beat_timestamps_ms: Optional[list[int]] = None,
        music: Optional[StoryboardMusic] = None,
    ) -> Storyboard:
        # 1. Analyze any unanalyzed uploads
        analyzed: list[AnalyzedUpload] = []
        for upload_id, path, cached in uploads:
            if cached is None:
                cached = await self.analyzer.analyze(path)
            analyzed.append(AnalyzedUpload(upload_id=upload_id, image_path=str(path), analysis=cached))

        # 2. Match images to slots
        match = self.matcher.match(template, analyzed)

        # 3. Build shots — no image generation at storyboard time; FAL handles it during render
        upload_by_id = {u.upload_id: u for u in analyzed}
        generated_paths: dict[str, Path] = {}
        for slot_id in match.needs_generation:
            slot = template.slot_by_id[slot_id]
            prompt = slot.generation_prompt or slot.description
            out_path = self.project_files.generated_dir(project.id) / f"{slot_id}.jpg"
            generated = await self.nano_banana.generate(
                prompt=prompt,
                out_path=out_path,
                aspect_ratio=template.aspect_ratio,
            )
            if generated:
                generated_paths[slot_id] = generated
            else:
                # generation failed — push to unfilled
                log.info("Generation failed for slot %s; marking unfilled", slot_id)

        # Final unfilled list
        final_unfilled = list(match.unfilled)
        for slot_id in match.needs_generation:
            if slot_id not in generated_paths:
                final_unfilled.append(slot_id)

        # 4. Pacing — compute timings (using audio if provided)
        timings = self.scheduler.schedule(template, str(audio_path_for_pacing) if audio_path_for_pacing else None)
        timing_by_slot = {t.slot_id: t for t in timings}

        shots: list[ResolvedShot] = []
        for slot in template.shot_slots:
            assigned_id = match.assignments.get(slot.slot_id)

            if assigned_id and assigned_id in upload_by_id:
                image_path = upload_by_id[assigned_id].image_path
                room_type = upload_by_id[assigned_id].analysis.room_type or slot.room_type
                is_generated = False
                source_upload_id = assigned_id
            elif slot.must_fill:
                # No matching upload — mark as generated (FAL t2v will fill during render)
                image_path = ""
                room_type = slot.room_type
                is_generated = True
                source_upload_id = None
            else:
                continue  # optional slot, drop it

            # Auto-select style recipe based on room type
            recipe = get_for_room(room_type, seed=i)

            timing = timing_by_slot.get(slot.slot_id)
            override = match.style_overrides.get(slot.slot_id, {})
            duration_sec = timing.duration_sec if timing else slot.duration_sec
            shots.append(
                ResolvedShot(
                    slot_id=slot.slot_id,
                    image_path=image_path,
                    start_time_sec=timing.start_time_sec if timing else 0.0,
                    duration_sec=timing.duration_sec if timing else slot.duration_sec,
                    motion=slot.motion,
                    motion_strength=slot.motion_strength,
                    transition_in=slot.transition_in,
                    color_grade=slot.color_grade,
                    text_overlay_id=slot.text_overlay_id,
                    rendered_text_overlay=rendered_text,
                    is_generated=is_generated,
                    source_upload_id=source_upload_id,
                    room_type=room_type,
                    style_recipe_id=recipe.style_id if recipe else None,
                )
            )
            timeline_t += duration_sec

        # Sort shots into house-tour order
        shots.sort(key=lambda s: ROOM_ORDER.get(s.room_type or "", 99))

        # Recompute start times after sort
        cursor = 0.0
        for s in shots:
            s.start_time_sec = cursor
            cursor += s.duration_sec

        total = cursor or template.target_duration_sec

        return Storyboard(
            storyboard_id=str(uuid.uuid4()),
            project_id=project.id,
            template_id=template.template_id,
            shots=shots,
            audio_cues=template.audio_cues,
            text_overlays=template.text_overlays,
            total_duration_sec=total,
            aspect_ratio=template.aspect_ratio,
            generated_slot_ids=[s.slot_id for s in shots if s.is_generated],
            unfilled_slot_ids=list(match.unfilled),
            notes=match.notes,
        )


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
        "Generate a realistic high-end real-estate listing image for a vertical cinematic reel. "
        "Use the uploaded reference photos as visual anchors for architecture, materials, lighting, "
        "and property identity when provided. Do not add text, logos, watermarks, distorted rooms, "
        "or impossible architecture. Keep it polished, commercial, dramatic, and soothing. "
        f"Needed shot: {slot_description}. {context_line} {style_line}"
    ).strip()
