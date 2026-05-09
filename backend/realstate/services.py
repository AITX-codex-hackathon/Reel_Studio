"""High-level service: tie agents + scheduler + pipeline together to build storyboards.

The API layer should only call into this; it shouldn't poke at agents directly.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from jinja2 import Environment, StrictUndefined, UndefinedError

from .agents.image_analyzer import ImageAnalyzer, ImageAnalysisResult
from .agents.shot_matcher import AnalyzedUpload, ShotMatcher
from .integrations.fal_image import FalImageClient
from .models.project import Project
from .models.storyboard import ResolvedShot, Storyboard, StoryboardMusic
from .models.template import Template
from .schedulers.pacing import PacingScheduler
from .storage.filesystem import ProjectFiles

log = logging.getLogger(__name__)


class StoryboardBuilder:
    """Builds a Storyboard from a Project, a Template, and a set of analyzed uploads."""

    def __init__(
        self,
        analyzer: Optional[ImageAnalyzer] = None,
        matcher: Optional[ShotMatcher] = None,
        scheduler: Optional[PacingScheduler] = None,
        image_generator: Optional[FalImageClient] = None,
        project_files: Optional[ProjectFiles] = None,
    ):
        self.analyzer = analyzer or ImageAnalyzer()
        self.matcher = matcher or ShotMatcher()
        self.scheduler = scheduler or PacingScheduler()
        self.image_generator = image_generator or FalImageClient()
        self.project_files = project_files or ProjectFiles()
        self.jinja = Environment(undefined=StrictUndefined)

    async def build(
        self,
        project: Project,
        template: Template,
        uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]],
        audio_path_for_pacing: Optional[Path] = None,
        beat_timestamps_ms: Optional[list[int]] = None,
        music: Optional[StoryboardMusic] = None,
    ) -> Storyboard:
        """Args:
            project: the property
            template: the chosen template
            uploads: list of (upload_id, image_path, cached_analysis_or_None)
            audio_path_for_pacing: optional, used by the scheduler for beat-snapping
        Returns: a fully resolved Storyboard.
        """
        # 1. Analyze any unanalyzed uploads
        analyzed: list[AnalyzedUpload] = []
        for upload_id, path, cached in uploads:
            if cached is None:
                cached = await self.analyzer.analyze(path)
            analyzed.append(AnalyzedUpload(upload_id=upload_id, image_path=str(path), analysis=cached))

        # 2. Match images to slots
        music_context = (
            f"{music.artist} - {music.title}, tempo {music.tempo or 'unknown'} BPM, "
            f"{music.beat_count} detected beats"
            if music
            else None
        )
        match = await self.matcher.match(template, analyzed, music_context=music_context)

        # 3. Generate fallback images for slots that need them
        upload_by_id = {u.upload_id: u for u in analyzed}
        reference_images = [Path(upload.image_path) for upload in analyzed[:3]]
        generated_paths: dict[str, Path] = {}
        for slot_id in match.needs_generation:
            slot = template.slot_by_id[slot_id]
            override = match.style_overrides.get(slot_id, {})
            prompt = _fallback_generation_prompt(
                project=project,
                slot_description=slot.generation_prompt or slot.description,
                style_notes=str(override.get("style_notes") or ""),
            )
            out_path = self.project_files.generated_dir(project.id) / f"{slot_id}.jpg"
            generated = await self.image_generator.generate(
                prompt=prompt,
                out_path=out_path,
                reference_images=reference_images or None,
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
        timings = self.scheduler.schedule(
            template,
            str(audio_path_for_pacing) if audio_path_for_pacing else None,
            beat_timestamps_ms=beat_timestamps_ms,
        )
        timing_by_slot = {t.slot_id: t for t in timings}

        # 5. Build ResolvedShot list
        property_ctx = {
            "address": project.address or "",
            "price": project.price or "",
            "beds": project.beds or "",
            "baths": project.baths or "",
            "sqft": f"{project.sqft:,}" if project.sqft else "",
            "name": project.name or "",
            "description": project.description or "",
        }
        text_overlay_by_id = template.text_overlay_by_id

        shots: list[ResolvedShot] = []
        ordered_slots = [template.slot_by_id[slot_id] for slot_id in match.slot_order if slot_id in template.slot_by_id]
        if not ordered_slots:
            ordered_slots = template.shot_slots

        timeline_t = 0.0
        for slot in ordered_slots:
            assigned_id = match.assignments.get(slot.slot_id)
            image_path: Optional[str] = None
            is_generated = False
            source_upload_id: Optional[str] = None

            if assigned_id and assigned_id in upload_by_id:
                image_path = upload_by_id[assigned_id].image_path
                source_upload_id = assigned_id
            elif slot.slot_id in generated_paths:
                image_path = str(generated_paths[slot.slot_id])
                is_generated = True
            else:
                continue  # slot dropped

            # Render text overlay (if any)
            rendered_text: Optional[str] = None
            if slot.text_overlay_id and slot.text_overlay_id in text_overlay_by_id:
                tmpl = text_overlay_by_id[slot.text_overlay_id]
                try:
                    rendered_text = self.jinja.from_string(tmpl.text_template).render(property=property_ctx)
                except UndefinedError as e:
                    log.warning("Text overlay %s missing data (%s); skipping", slot.text_overlay_id, e)
                    rendered_text = None

            timing = timing_by_slot.get(slot.slot_id)
            override = match.style_overrides.get(slot.slot_id, {})
            duration_sec = timing.duration_sec if timing else slot.duration_sec
            shots.append(
                ResolvedShot(
                    slot_id=slot.slot_id,
                    image_path=image_path,
                    start_time_sec=timeline_t,
                    duration_sec=duration_sec,
                    motion=override.get("motion", slot.motion),
                    motion_strength=override.get("motion_strength", slot.motion_strength),
                    transition_in=override.get("transition_in", slot.transition_in),
                    color_grade=override.get("color_grade", slot.color_grade),
                    text_overlay_id=slot.text_overlay_id,
                    rendered_text_overlay=rendered_text,
                    is_generated=is_generated,
                    source_upload_id=source_upload_id,
                )
            )
            timeline_t += duration_sec

        # Recompute total duration from actual shots
        if shots:
            total = max(s.end_time_sec for s in shots)
        else:
            total = template.target_duration_sec

        return Storyboard(
            storyboard_id=str(uuid.uuid4()),
            project_id=project.id,
            template_id=template.template_id,
            shots=shots,
            audio_cues=template.audio_cues,
            text_overlays=template.text_overlays,
            music=music,
            total_duration_sec=total,
            aspect_ratio=template.aspect_ratio,
            generated_slot_ids=list(generated_paths.keys()),
            unfilled_slot_ids=final_unfilled,
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
