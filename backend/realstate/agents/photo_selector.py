"""AI curation pass for large upload sets."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .openai_client import OpenAIClient, OpenAIUnavailable
from .prompt_standard import CORE_REEL_SOP, rubric_prompt_text
from .shot_matcher import AnalyzedUpload
from ..models.project import Project
from ..models.template import Template

log = logging.getLogger(__name__)


@dataclass
class PhotoSelectionResult:
    selected_upload_ids: list[str]
    rejected_upload_ids: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    concept_hint: str = ""
    notes: str = ""


class PhotoSelector:
    """Select the strongest story set after every upload has been analyzed."""

    def __init__(
        self,
        llm: Optional[OpenAIClient] = None,
        threshold: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        self.llm = llm or OpenAIClient()
        self.threshold = threshold or int(os.getenv("PHOTO_SELECTION_THRESHOLD", "20"))
        self.limit = limit or int(os.getenv("PHOTO_SELECTION_LIMIT", "16"))
        self.model = (
            os.getenv("OPENAI_PHOTO_SELECTOR_MODEL")
            or os.getenv("OPENAI_STORYBOARD_MODEL")
            or os.getenv("OPENAI_AGENT_MODEL")
            or os.getenv("OPENAI_MODEL")
        )

    async def select(
        self,
        *,
        project: Project,
        template: Template,
        uploads: list[AnalyzedUpload],
        music_context: str,
    ) -> PhotoSelectionResult:
        if len(uploads) <= self.threshold:
            return PhotoSelectionResult(
                selected_upload_ids=[upload.upload_id for upload in uploads],
                notes=f"Photo curation skipped: {len(uploads)} uploads is below threshold {self.threshold}.",
            )

        fallback = self._heuristic_select(uploads)
        if not self.llm.enabled:
            return fallback
        try:
            return await self._select_with_llm(project, template, uploads, music_context, fallback)
        except OpenAIUnavailable:
            return fallback
        except Exception as error:
            log.warning("OpenAI photo curation failed; using heuristic selection: %s", error)
            return fallback

    async def _select_with_llm(
        self,
        project: Project,
        template: Template,
        uploads: list[AnalyzedUpload],
        music_context: str,
        fallback: PhotoSelectionResult,
    ) -> PhotoSelectionResult:
        upload_ids = {upload.upload_id for upload in uploads}
        payload = {
            "project": {
                "name": project.name,
                "address": project.address,
                "description": project.description,
                "price": project.price,
                "beds": project.beds,
                "baths": project.baths,
                "sqft": project.sqft,
            },
            "template": {
                "id": template.template_id,
                "name": template.name,
                "description": template.description,
                "target_duration_sec": template.target_duration_sec,
                "shot_count": len(template.shot_slots),
                "slots": [
                    {
                        "slot_id": slot.slot_id,
                        "description": slot.description,
                        "room_type": slot.room_type,
                        "duration_sec": slot.duration_sec,
                    }
                    for slot in template.shot_slots
                ],
            },
            "music": music_context or "No selected track context.",
            "selection_rules": {
                "max_selected": min(self.limit, len(uploads)),
                "must_consider_every_upload": True,
                "goal": "Choose a tight 30-45 second reel set, usually 15-16 photos from a large upload batch.",
            },
            "uploads": [_upload_for_prompt(upload) for upload in uploads],
            "fallback_selected_upload_ids": fallback.selected_upload_ids,
        }
        system = (
            "You are the photo curation agent for EstateReelMaker. Your job happens after every "
            "uploaded image has already been visually analyzed. Consider the full upload set and choose "
            "the best images to form a premium real-estate mini-film. Prefer story coverage, visual "
            "quality, room variety, strong hero/detail/closing roles, source-safe geometry, and calm "
            "commercial cinematic potential. Reject duplicates, weak frames, risky masks, clutter, blur, "
            "crooked geometry, bad exposure, or photos that do not help the larger story.\n\n"
            f"{CORE_REEL_SOP}\n\n{rubric_prompt_text()}\n\n"
            "Return only valid JSON."
        )
        user = (
            "Select the best photos from this analyzed upload set. You must reason across all uploads, "
            "but return only JSON. Do not choose only the highest technical scores; build a balanced film "
            "with arrival, reveal, proof, texture, emotional breath, and closing memory when the uploads allow it. "
            "If the property has many similar photos, keep only the strongest representative frames. For 25-40 uploads, "
            "prefer about 15-16 selected photos unless the set is unusually weak or unusually strong. "
            "The selected_upload_ids should be ordered in the best rough story order before final storyboard matching.\n\n"
            "Return exactly this JSON shape:\n"
            "{\n"
            '  "selected_upload_ids": ["upload_id", "..."],\n'
            '  "rejected_upload_ids": ["upload_id", "..."],\n'
            '  "scores": {"upload_id": 0.0},\n'
            '  "concept_hint": "binding story suggestion based on the best photos",\n'
            '  "notes": "short curation explanation"\n'
            "}\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        text = await self.llm.message(
            system=system,
            user=user,
            max_tokens=5000,
            model=self.model,
        )
        data = _extract_json_object(text)
        selected = [upload_id for upload_id in data.get("selected_upload_ids", []) if upload_id in upload_ids]
        if not selected:
            selected = fallback.selected_upload_ids
        selected = _dedupe(selected)[: min(self.limit, len(uploads))]

        rejected = [upload_id for upload_id in data.get("rejected_upload_ids", []) if upload_id in upload_ids]
        rejected = [upload_id for upload_id in _dedupe(rejected) if upload_id not in selected]
        if not rejected:
            rejected = [upload.upload_id for upload in uploads if upload.upload_id not in selected]

        scores = {
            upload_id: _clamp_float(score, 0.0, 1.0)
            for upload_id, score in (data.get("scores") or {}).items()
            if upload_id in upload_ids
        }
        return PhotoSelectionResult(
            selected_upload_ids=selected,
            rejected_upload_ids=rejected,
            scores=scores,
            concept_hint=str(data.get("concept_hint") or "").strip()[:800],
            notes=str(data.get("notes") or "").strip()[:1000]
            or f"Curated {len(selected)} of {len(uploads)} analyzed uploads.",
        )

    def _heuristic_select(self, uploads: list[AnalyzedUpload]) -> PhotoSelectionResult:
        ranked = sorted(uploads, key=_upload_score, reverse=True)
        selected: list[str] = []
        room_counts: dict[str, int] = {}

        for upload in ranked:
            room = upload.analysis.room_type
            room_limit = 4 if room in {"exterior", "view", "living_room", "kitchen"} else 3
            if room_counts.get(room, 0) >= room_limit and len(selected) >= max(8, self.limit // 2):
                continue
            selected.append(upload.upload_id)
            room_counts[room] = room_counts.get(room, 0) + 1
            if len(selected) >= min(self.limit, len(uploads)):
                break

        if len(selected) < min(self.limit, len(uploads)):
            for upload in ranked:
                if upload.upload_id not in selected:
                    selected.append(upload.upload_id)
                if len(selected) >= min(self.limit, len(uploads)):
                    break

        rejected = [upload.upload_id for upload in uploads if upload.upload_id not in selected]
        return PhotoSelectionResult(
            selected_upload_ids=selected,
            rejected_upload_ids=rejected,
            scores={upload.upload_id: _upload_score(upload) for upload in uploads},
            notes=f"Heuristic curation selected {len(selected)} of {len(uploads)} analyzed uploads.",
        )


def _upload_for_prompt(upload: AnalyzedUpload) -> dict[str, Any]:
    analysis = upload.analysis
    return {
        "upload_id": upload.upload_id,
        "filename": Path(upload.image_path).name,
        "room_type": analysis.room_type,
        "quality_score": analysis.quality_score,
        "framing": analysis.framing,
        "lighting": analysis.lighting,
        "dominant_colors": analysis.dominant_colors,
        "suggested_motion": analysis.suggested_motion,
        "confidence": analysis.raw.get("confidence"),
        "secondary_room_types": analysis.raw.get("secondary_room_types", []),
        "usable_as": analysis.raw.get("usable_as", []),
        "cinematic_strengths": analysis.raw.get("cinematic_strengths", []),
        "defects": analysis.raw.get("defects", []),
        "notes": analysis.notes,
    }


def _upload_score(upload: AnalyzedUpload) -> float:
    analysis = upload.analysis
    score = float(analysis.quality_score)
    usable = set(analysis.raw.get("usable_as") or [])
    strengths = analysis.raw.get("cinematic_strengths") or []
    defects = analysis.raw.get("defects") or []
    if "hero" in usable:
        score += 0.16
    if "closing" in usable:
        score += 0.12
    if "detail" in usable:
        score += 0.08
    if analysis.framing == "wide":
        score += 0.08
    if analysis.lighting in {"golden_hour", "soft"}:
        score += 0.08
    score += min(0.12, 0.03 * len(strengths))
    score -= min(0.24, 0.06 * len(defects))
    return _clamp_float(score, 0.0, 1.0)


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _clamp_float(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(low, min(high, number))
