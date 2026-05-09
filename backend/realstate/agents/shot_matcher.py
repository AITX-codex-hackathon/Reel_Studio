"""Match analyzed images to template shot slots.

Two strategies, in order:
  1. Greedy heuristic: score each (slot, image) pair, then assign top scores
     under a constraint that no image is used more than `max_reuse` times.
  2. (Optional) LLM refinement: send the slot list + scored shortlist to
     the LLM for a final assignment that considers narrative flow.

Output: MatchResult with assignments + a list of slot_ids that need generation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .openai_client import OpenAIClient
from .image_analyzer import ImageAnalysisResult
from ..models.shot import ShotSlot
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
    notes: str = ""


class ShotMatcher:
    def __init__(self, llm: Optional[OpenAIClient] = None, max_reuse: int = 1):
        self.llm = llm
        self.max_reuse = max_reuse

    def match(self, template: Template, uploads: list[AnalyzedUpload]) -> MatchResult:
        if not uploads:
            return MatchResult(
                assignments={s.slot_id: None for s in template.shot_slots},
                needs_generation=[s.slot_id for s in template.shot_slots if s.must_fill and s.fallback_to_generated],
                unfilled=[s.slot_id for s in template.shot_slots if s.must_fill and not s.fallback_to_generated],
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
        for slot in template.shot_slots:
            best: tuple[float, Optional[str]] = (-1.0, None)
            for up in uploads:
                if usage[up.upload_id] >= self.max_reuse:
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
        return MatchResult(
            assignments=assignments,
            needs_generation=needs_gen,
            unfilled=unfilled,
            notes=notes,
        )

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
