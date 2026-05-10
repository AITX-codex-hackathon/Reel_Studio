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
from .prompt_standard import CORE_REEL_SOP, STORYBOARD_AGENT_SOP, rubric_prompt_text, transition_reference_prompt_text
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
    # per-slot style/camera overrides: motion, motion_strength, transition_in, color_grade, scene intent, masks
    style_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    creative_brief: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


class ShotMatcher:
    def __init__(self, llm: Optional[OpenAIClient] = None, max_reuse: int = 1):
        self.llm = llm or OpenAIClient()
        self.max_reuse = max_reuse
        self.storyboard_model = (
            os.getenv("OPENAI_STORYBOARD_MODEL")
            or os.getenv("OPENAI_AGENT_MODEL")
            or os.getenv("OPENAI_MODEL")
        )

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
                creative_brief=_fallback_creative_brief(template, upload_count=0),
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
            style_overrides=_fallback_style_overrides(template),
            creative_brief=_fallback_creative_brief(template, upload_count=len(uploads)),
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
                "Every storyboard must have one binding concept that ties all photos into a single big story.",
                "Each photo must be treated as a scene with narrative purpose, beat timing, masking, and continuity.",
                "Style notes must tell FAL how to move the camera while preserving the source image geometry.",
                "Transitions must be motivated by audio, geometry, light, or camera direction; never random.",
            ],
        }
        system = (
            "You are the senior editor agent for an AI real-estate reel maker. "
            "You replace a human editor and cinematographer by deciding story order, shot-to-photo "
            "assignment, camera movement, transition grammar, beat feel, and per-shot visual direction. "
            "The work must feel like a premium commercial listing film: cinematic, dramatic, polished, "
            "spacious, soothing, and expensive. Stay grounded in the actual uploaded images. Never fake "
            "a room just because the template mentions it; if the room is missing, reuse a real upload "
            "as an honest bridge, exterior, detail, or atmosphere shot.\n\n"
            f"{CORE_REEL_SOP}\n\n{STORYBOARD_AGENT_SOP}\n\n"
            f"{rubric_prompt_text()}\n\n"
            f"{transition_reference_prompt_text()}\n\n"
            "Return only valid JSON."
        )
        user = (
            "Create a comprehensive editor plan from this JSON. First decide the big-picture concept "
            "that turns these uploads into one premium mini-film. Then assign scenes, order them, and "
            "write the shot direction. For each slot_id, assign either an upload_id or null. If there is "
            "at least one uploaded photo, avoid null and reuse real uploads as anchors, even when the "
            "template asks for a room type that is absent. Use null only as a last resort.\n\n"
            "The plan must be detailed enough for downstream AI agents and FAL image-to-video. Each "
            "scene must explain the purpose of the shot in the larger story, the camera path over the "
            "duration, the beat/cut logic, source-safe mask holdouts, safe animated regions, transition "
            "motivation, continuity, and negative constraints. Do not write generic transitions. Do not "
            "write filler like 'make it cinematic'. Every millisecond should have intent. The rubric "
            "object for each slot is mandatory and must be concrete enough for a human editor and FAL.\n\n"
            "Style direction must stay calm commercial luxury: smooth, spacious, dramatic, soothing, "
            "editorial, and expensive. Avoid chaotic transitions, hype music-video language, aggressive "
            "camera moves, trap/hip-hop cues, nightclub impact hits, and fake architecture. Use the "
            "transition reference to design seamless motivated transitions: matched vectors, masked "
            "foreground wipes, glass/door passes, time-of-day match cuts, reflection/sky/water bridges, "
            "velocity-matched dissolves, or invisible cuts during blur. Every camera move must complement "
            "the photo, the neighboring scene, and the beat analysis; never choose motion just because it sounds impressive.\n\n"
            "Return exactly this JSON shape:\n"
            "{\n"
            '  "creative_brief": {\n'
            '    "concept_title": "short binding concept title",\n'
            '    "logline": "one sentence tying the whole reel together",\n'
            '    "visual_theme": "consistent visual grammar and camera language",\n'
            '    "emotional_arc": "how the feeling evolves from first frame to last",\n'
            '    "music_strategy": "how the selected track/beat timestamps drive cuts calmly",\n'
            '    "continuity_rules": ["rule", "..."]\n'
            "  },\n"
            '  "assignments": {"slot_id": "upload_id_or_null"},\n'
            '  "slot_order": ["slot_id", "..."],\n'
            '  "style_overrides": {\n'
            '    "slot_id": {\n'
            '      "motion": "one allowed motion",\n'
            '      "motion_strength": 0.0,\n'
            '      "transition_in": "one allowed transition",\n'
            '      "color_grade": "warm_cinematic | cool_modern | warm_lifestyle | null",\n'
            '      "scene_purpose": "the narrative job of this scene inside the binding concept",\n'
            '      "style_notes": "4-8 dense sentences of precise cinematography and FAL direction",\n'
            '      "beat_plan": "beginning/midpoint/end timing and audio cut intention",\n'
            '      "masking_plan": "source-safe holdouts and safe animated regions",\n'
            '      "transition_plan": "motivated transition logic into/out of this scene",\n'
            '      "continuity_notes": "geometry/light/color/camera-direction continuity requirements",\n'
            '      "rubric": {\n'
            '        "SCENE_ID": "01",\n'
            '        "NARRATIVE_THESIS": "why this scene matters in the whole film",\n'
            '        "TEMPORAL_AUDIO_SYNC": {\n'
            '          "DURATION_MS": "exact duration in ms",\n'
            '          "AUDIO_BEAT_MAP": "beat/swell/cut timing across the shot",\n'
            '          "CUT_REACTION": "how motion reacts to the audio"\n'
            "        },\n"
            '        "OPTICS_AND_RIGGING": {\n'
            '          "LENS_MM": "specific lens feel",\n'
            '          "APERTURE": "depth of field",\n'
            '          "CAMERA_POSITION": "physical placement relative to subject"\n'
            "        },\n"
            '        "KINETIC_PATHWAY": {\n'
            '          "PRIMARY_MOVEMENT": "pan/tilt/dolly/truck/pedestal/roll",\n'
            '          "PARALLAX_TARGET": "foreground/background depth relationship",\n'
            '          "EASING_CURVE": "linear/ease-in/ease-out/bezier"\n'
            "        },\n"
            '        "PRESERVATION_AND_MASKING": {\n'
            '          "STRICT_ZONES": "specific source-image geometry that must not warp",\n'
            '          "ALLOWED_FLEXIBILITY": "safe motion regions such as sky/water/foliage/light"\n'
            "        },\n"
            '        "SEAMLESS_TRANSITION_ARCHITECTURE": {\n'
            '          "INGRESS_SEAM": "how this scene receives previous momentum",\n'
            '          "EGRESS_SEAM": "how this scene sets up the next visual vector"\n'
            "        },\n"
            '        "FAL_GENERATION_PROMPT": "1800-2200 character provider-ready prompt"\n'
            "      }\n"
            "    }\n"
            "  },\n"
            '  "notes": "short explanation"\n'
            "}\n\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        text = await self.llm.message(
            system=system,
            user=user,
            max_tokens=7000,
            model=self.storyboard_model,
            temperature=0.2,
        )
        data = _extract_json_object(text)
        creative_brief = _clean_creative_brief(data.get("creative_brief")) or fallback.creative_brief

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
            color_grade = override.get("color_grade")
            if color_grade is not None and str(color_grade).strip().lower() not in {"", "null", "none"}:
                cleaned["color_grade"] = str(color_grade).strip()
            for field_name, limit in _STYLE_TEXT_FIELDS.items():
                if override.get(field_name):
                    cleaned[field_name] = _clean_text(override[field_name], limit)
            rubric = _clean_rubric_plan(override.get("rubric") or override.get("rubric_plan"))
            if rubric:
                cleaned["rubric_plan"] = rubric
            if cleaned:
                style_overrides[slot_id] = cleaned
        for slot_id, fallback_override in fallback.style_overrides.items():
            style_overrides.setdefault(slot_id, fallback_override)

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
            creative_brief=creative_brief,
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


_STYLE_TEXT_FIELDS: dict[str, int] = {
    "scene_purpose": 1000,
    "style_notes": 2400,
    "beat_plan": 1400,
    "masking_plan": 1800,
    "transition_plan": 1400,
    "continuity_notes": 1400,
}


def _fallback_creative_brief(template: Template, upload_count: int) -> dict[str, Any]:
    duration = f"{template.target_duration_sec:.0f}s" if template.target_duration_sec else "short"
    sparse_note = (
        "Because the upload set is sparse, repeat real photos with different camera intentions instead of inventing rooms."
        if upload_count and upload_count < 5
        else "Use the available photos as a guided property walk-through."
    )
    return {
        "concept_title": f"{template.name}: quiet arrival",
        "logline": (
            f"A {duration} calm commercial property film that moves from first impression to lived-in atmosphere "
            "and leaves the viewer with a polished memory of the home."
        ),
        "visual_theme": (
            "Controlled architectural camera movement, warm refined light, stable vertical lines, soft parallax, "
            "and clean motivated cuts that make the listing feel spacious and premium."
        ),
        "emotional_arc": "Begin with orientation, move into invitation and texture, then close with calm confidence.",
        "music_strategy": (
            "Let beat timestamps guide scene entrances and exits without forcing hype edits; use downbeats for reveals "
            "and softer measures for details and transitions."
        ),
        "continuity_rules": [
            "Preserve the source photo as the visual truth.",
            "Keep camera direction and light behavior smooth from scene to scene.",
            "Do not add missing rooms, people, signage, logos, or impossible architecture.",
            sparse_note,
        ],
    }


def _fallback_style_overrides(template: Template) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    total = max(len(template.shot_slots), 1)
    for index, slot in enumerate(template.shot_slots):
        entrance = "opening reveal" if index == 0 else "continuity scene"
        exit_note = "final held memory" if index == total - 1 else "motivated handoff to the next space"
        room = (slot.room_type or "property detail").replace("_", " ")
        overrides[slot.slot_id] = {
            "scene_purpose": (
                f"{entrance.capitalize()} for the {room}: make this frame serve the larger property story, "
                "either by establishing scale, inviting the viewer deeper, proving material quality, or creating a calm emotional pause."
            ),
            "style_notes": (
                "Use a controlled real-estate camera move with lens-stable architecture and a deliberate beginning, midpoint, and exit. "
                "Start from the strongest readable composition in the source photo, move slowly enough that vertical lines remain trustworthy, "
                "and let parallax come from safe foreground/background separation rather than warping walls or fixtures. "
                "Favor premium commercial restraint: soft reflected light, elegant shadows, natural depth, and a composed final frame that can cut cleanly."
            ),
            "beat_plan": (
                "Hold the first fraction of the shot long enough for orientation, let the camera movement peak near the strongest musical beat, "
                f"and use the final half-second as a clean {exit_note}. Avoid sudden speed changes unless the audio provides a gentle downbeat."
            ),
            "masking_plan": (
                "Hard holdout architecture, window frames, floor edges, ceiling lines, furniture geometry, readable text, logos, people, and fixtures. "
                "Allow only subtle masked motion in light, shadows, reflections, curtains, foliage, water, sky, fireplace, or camera parallax where the source image supports it."
            ),
            "transition_plan": (
                f"Use {slot.transition_in.value} only if it supports the geometry and light of the neighboring shot; otherwise keep the cut clean and motivated by the music."
            ),
            "continuity_notes": (
                "Maintain calm camera direction, realistic exposure, consistent color temperature, and trustworthy room scale. "
                "If the source image is reused, change the intention and crop path without pretending it is a different room."
            ),
            "rubric_plan": _fallback_rubric_plan(slot, index=index, total=total),
        }
    return overrides


def _fallback_rubric_plan(slot: ShotSlot, index: int, total: int) -> dict[str, Any]:
    duration_ms = int(max(2.5, slot.duration_sec) * 1000)
    scene_id = f"{index + 1:02d}"
    room = (slot.room_type or "property detail").replace("_", " ")
    return {
        "SCENE_ID": scene_id,
        "NARRATIVE_THESIS": (
            f"Scene {scene_id} uses the {room} image to serve the larger property arc with a clear reveal, "
            "proof point, emotional breath, or closing memory."
        ),
        "TEMPORAL_AUDIO_SYNC": {
            "DURATION_MS": f"{duration_ms}ms",
            "AUDIO_BEAT_MAP": "Orient for the first 20%, let the main motion breathe through the middle, and settle before the cut.",
            "CUT_REACTION": "Use the strongest downbeat or phrase change for the scene handoff; avoid cutting on every beat.",
        },
        "OPTICS_AND_RIGGING": {
            "LENS_MM": "24-35mm architectural lens feel",
            "APERTURE": "f/5.6-f/8 deep enough to keep architecture trustworthy",
            "CAMERA_POSITION": "Stable real-estate camera height aligned to the dominant geometry",
        },
        "KINETIC_PATHWAY": {
            "PRIMARY_MOVEMENT": slot.motion.value,
            "PARALLAX_TARGET": "Use only true foreground/background separation visible in the source photo.",
            "EASING_CURVE": "Ease-in/ease-out with no sudden whip movement",
        },
        "PRESERVATION_AND_MASKING": {
            "STRICT_ZONES": "Walls, windows, floor edges, ceiling lines, furniture, fixtures, readable text, logos, people, and architectural perspective.",
            "ALLOWED_FLEXIBILITY": "Subtle light, shadow, reflections, curtains, foliage, water, sky, fireplace, or camera parallax supported by the source image.",
        },
        "SEAMLESS_TRANSITION_ARCHITECTURE": {
            "INGRESS_SEAM": "Receive the prior scene through matched light, geometry, or camera direction.",
            "EGRESS_SEAM": "End on a stable frame that hands off cleanly to the next scene.",
        },
        "FAL_GENERATION_PROMPT": "Premium real-estate image-to-video shot; preserve source geometry and identity; smooth calm commercial motion; no fake rooms or warped architecture.",
    }


def _clean_creative_brief(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    continuity = value.get("continuity_rules") or []
    if not isinstance(continuity, list):
        continuity = [continuity]
    return {
        "concept_title": _clean_text(value.get("concept_title"), 180),
        "logline": _clean_text(value.get("logline"), 500),
        "visual_theme": _clean_text(value.get("visual_theme"), 800),
        "emotional_arc": _clean_text(value.get("emotional_arc"), 800),
        "music_strategy": _clean_text(value.get("music_strategy"), 800),
        "continuity_rules": [_clean_text(item, 260) for item in continuity if _clean_text(item, 260)][:8],
    }


def _clean_rubric_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        clean_key = _clean_text(key, 80)
        if not clean_key:
            continue
        if isinstance(item, dict):
            nested = {
                _clean_text(nested_key, 80): _clean_text(nested_value, 700)
                for nested_key, nested_value in item.items()
                if _clean_text(nested_key, 80)
            }
            if nested:
                cleaned[clean_key] = nested
        else:
            cleaned[clean_key] = _clean_text(item, 2200 if clean_key == "FAL_GENERATION_PROMPT" else 900)
    return cleaned


def _clean_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip()


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
