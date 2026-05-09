"""Match analyzed images to template shot slots.

Two strategies, in order:
  1. Greedy heuristic: score each (slot, image) pair, then assign top scores
     under a constraint that no image is used more than `max_reuse` times.
  2. (Optional) LLM refinement: send the slot list + scored shortlist to
     the LLM for a final assignment that considers narrative flow.

Output: MatchResult with assignments + a list of slot_ids that need generation.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .openai_client import OpenAIClient, OpenAIUnavailable
from .image_analyzer import ImageAnalysisResult
from ..models.shot import MotionPreset, ShotSlot, TransitionType
from ..models.template import Template

log = logging.getLogger(__name__)


@dataclass
class AnalyzedUpload:
    upload_id: str
    image_path: str
    analysis: ImageAnalysisResult


@dataclass
class MatchResult:
    # slot_id -> upload_id (or None if no upload matched)
    assignments: dict[str, Optional[str]]
    # slot_ids that need generative fallback
    needs_generation: list[str] = field(default_factory=list)
    # slot_ids that are unfilled (not generated, not assigned)
    unfilled: list[str] = field(default_factory=list)
    # editor-approved story order. Missing slot ids are appended in template order.
    slot_order: list[str] = field(default_factory=list)
    # per-slot style/camera overrides: motion, motion_strength, transition_in, color_grade, style_notes
    style_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: str = ""


class ShotMatcher:
    def __init__(self, llm: Optional[OpenAIClient] = None, max_reuse: int = 1):
        self.llm = llm or OpenAIClient()
        self.max_reuse = max_reuse

    async def match(
        self,
        template: Template,
        uploads: list[AnalyzedUpload],
        music_context: Optional[str] = None,
    ) -> MatchResult:
        fallback = self._heuristic_match(template, uploads)
        if not uploads or not self.llm.enabled:
            return fallback
        try:
            return await self._match_with_llm(template, uploads, fallback, music_context)
        except OpenAIUnavailable:
            return fallback
        except Exception as error:
            log.warning("OpenAI storyboard refinement failed, using heuristic match: %s", error)
            return fallback

    def _heuristic_match(self, template: Template, uploads: list[AnalyzedUpload]) -> MatchResult:
        if not uploads:
            return MatchResult(
                assignments={s.slot_id: None for s in template.shot_slots},
                needs_generation=[s.slot_id for s in template.shot_slots if s.must_fill and s.fallback_to_generated],
                unfilled=[s.slot_id for s in template.shot_slots if s.must_fill and not s.fallback_to_generated],
                slot_order=[s.slot_id for s in template.shot_slots],
                notes="No uploads provided.",
            )

        # Build score matrix
        scores: dict[tuple[str, str], float] = {}
        for slot in template.shot_slots:
            for up in uploads:
                scores[(slot.slot_id, up.upload_id)] = self._score(slot, up)

        # Greedy assignment: for each slot in order, pick best unused upload
        usage: dict[str, int] = {u.upload_id: 0 for u in uploads}
        assignments: dict[str, Optional[str]] = {}
        max_reuse = self._effective_max_reuse(len(uploads), len(template.shot_slots))
        for slot in template.shot_slots:
            best: tuple[float, Optional[str]] = (-1.0, None)
            for up in uploads:
                if usage[up.upload_id] >= max_reuse:
                    continue
                s = scores[(slot.slot_id, up.upload_id)]
                if s > best[0]:
                    best = (s, up.upload_id)

            # Threshold: a score below 0.15 means "doesn't fit" — leave unassigned
            if best[1] is not None and best[0] >= 0.15:
                assignments[slot.slot_id] = best[1]
                usage[best[1]] += 1
            else:
                assignments[slot.slot_id] = None

        needs_gen: list[str] = []
        unfilled: list[str] = []
        for slot in template.shot_slots:
            if assignments[slot.slot_id] is None:
                if slot.must_fill and slot.fallback_to_generated:
                    needs_gen.append(slot.slot_id)
                elif slot.must_fill:
                    unfilled.append(slot.slot_id)
                # else: optional slot, ok to drop

        notes = (
            f"Matched {sum(1 for v in assignments.values() if v)} / {len(template.shot_slots)} slots. "
            f"Need generation: {len(needs_gen)}. Unfilled (no fallback): {len(unfilled)}."
        )
        if len(uploads) <= 2:
            notes += " Low-image fallback active: uploaded photos are anchors and missing slots are generated."
        return MatchResult(
            assignments=assignments,
            needs_generation=needs_gen,
            unfilled=unfilled,
            slot_order=[s.slot_id for s in template.shot_slots],
            notes=notes,
        )

    async def _match_with_llm(
        self,
        template: Template,
        uploads: list[AnalyzedUpload],
        fallback: MatchResult,
        music_context: Optional[str],
    ) -> MatchResult:
        upload_ids = {upload.upload_id for upload in uploads}
        slot_ids = {slot.slot_id for slot in template.shot_slots}

        payload = {
            "template": {
                "id": template.template_id,
                "name": template.name,
                "description": template.description,
                "duration_sec": template.target_duration_sec,
                "pacing_mode": template.pacing_mode,
                "aspect_ratio": template.aspect_ratio,
            },
            "music": music_context or "No selected track context.",
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "description": slot.description,
                    "room_type": slot.room_type,
                    "duration_sec": slot.duration_sec,
                    "default_motion": slot.motion,
                    "default_transition": slot.transition_in,
                    "must_fill": slot.must_fill,
                    "fallback_to_generated": slot.fallback_to_generated,
                }
                for slot in template.shot_slots
            ],
            "uploads": [
                {
                    "upload_id": upload.upload_id,
                    "room_type": upload.analysis.room_type,
                    "quality_score": upload.analysis.quality_score,
                    "framing": upload.analysis.framing,
                    "lighting": upload.analysis.lighting,
                    "suggested_motion": upload.analysis.suggested_motion,
                    "notes": upload.analysis.notes,
                }
                for upload in uploads
            ],
            "heuristic_assignments": fallback.assignments,
            "allowed_motion": [motion.value for motion in MotionPreset],
            "allowed_transitions": [transition.value for transition in TransitionType],
        }
        system = (
            "You are the senior editor agent for an AI real-estate reel maker. "
            "You replace a human editor by deciding story order, shot-to-photo assignment, "
            "where generative fallback is needed, camera motion, transition style, and pacing feel. "
            "Use OpenAI reasoning to make a calm commercial cinematic listing reel from static images. "
            "Return only valid JSON."
        )
        user = (
            "Create an editor plan from this JSON. For each slot_id, assign either an upload_id or null. "
            "Use null when fal.ai should generate a missing angle/detail/reveal shot. If there are only "
            "1 or 2 uploaded photos, reuse the best uploads sparingly as anchors and generate the rest. "
            "Choose a slot_order that tells a coherent real-estate story. Avoid chaotic transitions. "
            "Style should feel commercial, dramatic, polished, and soothing.\n\n"
            "Return exactly this JSON shape:\n"
            "{\n"
            '  "assignments": {"slot_id": "upload_id_or_null"},\n'
            '  "slot_order": ["slot_id", "..."],\n'
            '  "style_overrides": {\n'
            '    "slot_id": {\n'
            '      "motion": "one allowed motion",\n'
            '      "motion_strength": 0.0,\n'
            '      "transition_in": "one allowed transition",\n'
            '      "color_grade": "warm_cinematic | cool_modern | warm_lifestyle | null",\n'
            '      "style_notes": "short camera-angle/editorial direction"\n'
            "    }\n"
            "  },\n"
            '  "notes": "short explanation"\n'
            "}\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        text = await self.llm.message(system=system, user=user, max_tokens=4096)
        data = _extract_json_object(text)

        assignments = dict(fallback.assignments)
        for slot_id, upload_id in (data.get("assignments") or {}).items():
            if slot_id not in slot_ids:
                continue
            assignments[slot_id] = upload_id if upload_id in upload_ids else None

        slot_order = [slot_id for slot_id in data.get("slot_order") or [] if slot_id in slot_ids]
        for slot in template.shot_slots:
            if slot.slot_id not in slot_order:
                slot_order.append(slot.slot_id)

        style_overrides: dict[str, dict[str, Any]] = {}
        for slot_id, override in (data.get("style_overrides") or {}).items():
            if slot_id not in slot_ids or not isinstance(override, dict):
                continue
            cleaned: dict[str, Any] = {}
            if override.get("motion") in {motion.value for motion in MotionPreset}:
                cleaned["motion"] = override["motion"]
            try:
                cleaned["motion_strength"] = max(0.0, min(1.0, float(override.get("motion_strength"))))
            except (TypeError, ValueError):
                pass
            if override.get("transition_in") in {transition.value for transition in TransitionType}:
                cleaned["transition_in"] = override["transition_in"]
            if override.get("color_grade") is not None:
                cleaned["color_grade"] = str(override.get("color_grade"))
            if override.get("style_notes"):
                cleaned["style_notes"] = str(override["style_notes"])[:500]
            if cleaned:
                style_overrides[slot_id] = cleaned

        needs_gen, unfilled = self._classify_unassigned(template, assignments)
        notes = str(data.get("notes") or "").strip()
        if notes:
            notes = f"OpenAI editor plan: {notes}"
        else:
            notes = "OpenAI editor plan applied."
        return MatchResult(
            assignments=assignments,
            needs_generation=needs_gen,
            unfilled=unfilled,
            slot_order=slot_order,
            style_overrides=style_overrides,
            notes=notes,
        )

    def _effective_max_reuse(self, upload_count: int, slot_count: int) -> int:
        if upload_count <= 0:
            return 0
        if upload_count == 1:
            return min(4, slot_count)
        if upload_count == 2:
            return min(3, max(1, slot_count // upload_count))
        if upload_count < max(4, slot_count // 2):
            return 2
        return self.max_reuse

    def _classify_unassigned(
        self,
        template: Template,
        assignments: dict[str, Optional[str]],
    ) -> tuple[list[str], list[str]]:
        needs_gen: list[str] = []
        unfilled: list[str] = []
        for slot in template.shot_slots:
            if assignments.get(slot.slot_id) is None:
                if slot.must_fill and slot.fallback_to_generated:
                    needs_gen.append(slot.slot_id)
                elif slot.must_fill:
                    unfilled.append(slot.slot_id)
        return needs_gen, unfilled

    def _score(self, slot: ShotSlot, up: AnalyzedUpload) -> float:
        """Return a 0..1 score for how well the upload fits the slot."""
        score = 0.0

        # Room type — biggest signal
        if slot.room_type and up.analysis.room_type == slot.room_type:
            score += 0.55
        elif slot.room_type:
            # near-miss bonuses
            near = _NEAR_ROOMS.get(slot.room_type, set())
            if up.analysis.room_type in near:
                score += 0.25

        # Framing alignment from description heuristics
        desc_l = slot.description.lower()
        if "wide" in desc_l and up.analysis.framing == "wide":
            score += 0.10
        if any(k in desc_l for k in ("detail", "close")) and up.analysis.framing in ("detail", "close"):
            score += 0.15
        if "wide" not in desc_l and "detail" not in desc_l and up.analysis.framing == "medium":
            score += 0.05

        # Quality always counts
        score += 0.30 * up.analysis.quality_score

        return min(1.0, score)


# Soft adjacencies — close-enough rooms when exact match fails
_NEAR_ROOMS: dict[str, set[str]] = {
    "exterior": {"backyard", "view"},
    "foyer": {"living_room"},
    "kitchen": {"dining"},
    "living_room": {"dining", "foyer"},
    "bedroom": {"detail"},
    "bathroom": {"detail"},
    "backyard": {"exterior", "view", "amenity"},
    "view": {"exterior", "backyard"},
    "amenity": {"backyard", "exterior"},
    "lifestyle": {"detail", "living_room"},
    "detail": {"kitchen", "living_room", "bedroom", "bathroom"},
    "dining": {"living_room", "kitchen"},
}


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise
