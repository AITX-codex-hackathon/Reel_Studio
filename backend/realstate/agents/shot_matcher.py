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
import os
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
        self.storyboard_model = os.getenv("OPENAI_STORYBOARD_MODEL") or os.getenv("OPENAI_MODEL")

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

        # Greedy assignment: for each slot in order, pick the best upload. When the
        # upload set is small, reuse real photos instead of creating fake rooms.
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

            # Prefer fit, but do not generate missing rooms just because the
            # uploaded set is sparse. Reuse the strongest real anchor.
            if best[1] is not None and (best[0] >= 0.15 or slot.must_fill):
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
            notes += " Low-image fallback active: uploaded photos are reused as grounded anchors."
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
                    "confidence": upload.analysis.raw.get("confidence"),
                    "secondary_room_types": upload.analysis.raw.get("secondary_room_types", []),
                    "usable_as": upload.analysis.raw.get("usable_as", []),
                    "cinematic_strengths": upload.analysis.raw.get("cinematic_strengths", []),
                    "defects": upload.analysis.raw.get("defects", []),
                    "notes": upload.analysis.notes,
                }
                for upload in uploads
            ],
            "heuristic_assignments": fallback.assignments,
            "allowed_motion": [motion.value for motion in MotionPreset],
            "allowed_transitions": [transition.value for transition in TransitionType],
            "hard_rules": [
                "Storyboard must be grounded in the actual uploaded photos.",
                "Do not invent missing rooms at storyboard time when at least one upload exists.",
                "Use null only when there are no usable uploads at all for a required generated slot.",
                "If a slot's requested room is absent, reuse the best real upload as a cinematic bridge/detail shot.",
                "Style notes must tell FAL how to move the camera while preserving the source image geometry.",
            ],
        }
        system = (
            "You are the senior editor agent for an AI real-estate reel maker. "
            "You replace a human editor and cinematographer by deciding story order, shot-to-photo "
            "assignment, camera movement, transition grammar, beat feel, and per-shot visual direction. "
            "The work must feel like a premium commercial listing film: cinematic, dramatic, polished, "
            "spacious, soothing, and expensive. Stay grounded in the actual uploaded images. Never fake "
            "a room just because the template mentions it; if the room is missing, reuse a real upload "
            "as an honest bridge, exterior, detail, or atmosphere shot. Return only valid JSON."
        )
        user = (
            "Create an editor plan from this JSON. For each slot_id, assign either an upload_id or null. "
            "If there is at least one uploaded photo, avoid null and reuse real uploads as anchors, even "
            "when the template asks for a room type that is absent. Use null only as a last resort. "
            "Choose a slot_order that tells a coherent property story from what actually exists. "
            "Avoid chaotic transitions, hype music-video language, and aggressive camera moves.\n\n"
            "For style_overrides, be extremely descriptive. Each style_notes value should be 2-4 dense "
            "sentences of cinematography direction for FAL: camera height, lens feel, movement path, "
            "foreground/background parallax, lighting behavior, atmosphere, transition intention, beat "
            "relationship, and what must remain unchanged from the source photo. Use calm commercial "
            "luxury language, not generic words like 'nice' or 'cinematic shot'.\n\n"
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
        text = await self.llm.message(system=system, user=user, max_tokens=4096, model=self.storyboard_model)
        data = _extract_json_object(text)

        assignments = dict(fallback.assignments)
        for slot_id, upload_id in (data.get("assignments") or {}).items():
            if slot_id not in slot_ids:
                continue
            assignments[slot_id] = upload_id if upload_id in upload_ids else None
        if uploads:
            assignments = self._ensure_real_uploads(template, uploads, assignments)

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
                cleaned["style_notes"] = str(override["style_notes"])[:1200]
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
            return slot_count
        if upload_count == 2:
            return max(1, (slot_count + upload_count - 1) // upload_count)
        if upload_count < slot_count:
            return max(2, (slot_count + upload_count - 1) // upload_count)
        return self.max_reuse

    def _ensure_real_uploads(
        self,
        template: Template,
        uploads: list[AnalyzedUpload],
        assignments: dict[str, Optional[str]],
    ) -> dict[str, Optional[str]]:
        """Replace null required slots with the best real upload to avoid hallucinated filler."""
        out = dict(assignments)
        for slot in template.shot_slots:
            if not slot.must_fill or out.get(slot.slot_id):
                continue
            out[slot.slot_id] = max(uploads, key=lambda upload: self._score(slot, upload)).upload_id
        return out

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
            secondary = set(up.analysis.raw.get("secondary_room_types") or [])
            if slot.room_type in secondary:
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

        usable_as = set(up.analysis.raw.get("usable_as") or [])
        if "hero" in desc_l and "hero" in usable_as:
            score += 0.10
        if any(k in desc_l for k in ("closing", "final", "end")) and "closing" in usable_as:
            score += 0.10
        if up.analysis.raw.get("defects"):
            score -= min(0.12, 0.03 * len(up.analysis.raw.get("defects") or []))

        return max(0.0, min(1.0, score))


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
