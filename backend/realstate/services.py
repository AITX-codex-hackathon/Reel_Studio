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
from .integrations.nano_banana import NanoBananaClient
from .models.project import Project
from .models.shot import MotionPreset, TransitionType
from .models.storyboard import ResolvedShot, Storyboard
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
        nano_banana: Optional[NanoBananaClient] = None,
        project_files: Optional[ProjectFiles] = None,
    ):
        self.analyzer = analyzer or ImageAnalyzer()
        self.matcher = matcher or ShotMatcher()
        self.scheduler = scheduler or PacingScheduler()
        self.nano_banana = nano_banana or NanoBananaClient()
        self.project_files = project_files or ProjectFiles()
        self.jinja = Environment(undefined=StrictUndefined)

    async def build(
        self,
        project: Project,
        template: Template,
        uploads: list[tuple[str, Path, Optional[ImageAnalysisResult]]],
        audio_path_for_pacing: Optional[Path] = None,
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
        match = self.matcher.match(template, analyzed)

        # 3. Generate fallback images for slots that need them
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
        for slot in template.shot_slots:
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
                )
            )

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
            total_duration_sec=total,
            aspect_ratio=template.aspect_ratio,
            generated_slot_ids=list(generated_paths.keys()),
            unfilled_slot_ids=final_unfilled,
            notes=match.notes,
        )
