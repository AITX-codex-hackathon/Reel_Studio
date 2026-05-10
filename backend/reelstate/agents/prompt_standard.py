"""Shared prompt standards for EstateReelMaker agents.

The goal is to keep every agent on the same directing language: evidence first,
one binding concept, scene-by-scene intention, and source-safe cinematic motion.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_RUBRIC_PATH = Path(__file__).resolve().parents[3] / "Rubric.json"
_TRANSITIONS_PATH = Path(__file__).resolve().parents[3] / "transitions.txt"
_VIDEO_AGENT_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "video_agent_schema.json"


@lru_cache(maxsize=1)
def load_rubric() -> dict[str, Any]:
    try:
        with open(_RUBRIC_PATH, encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def rubric_prompt_text() -> str:
    rubric = load_rubric()
    if not rubric:
        return ""
    return (
        "Mandatory scene rubric. Every selected storyboard scene must fill this structure with "
        "concrete, source-grounded direction:\n"
        f"{json.dumps(rubric, indent=2)}"
    )


@lru_cache(maxsize=1)
def load_transition_reference() -> str:
    try:
        return _TRANSITIONS_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def transition_reference_prompt_text(max_chars: int = 12000) -> str:
    reference = load_transition_reference()
    if not reference:
        return ""
    reference = reference[:max_chars].strip()
    return (
        "Competitive transition reference from transitions.txt. Use this as a vocabulary of "
        "professional transition architecture, not as permission to copy hype pacing. Extract the "
        "principles: spatial mapping, matched camera vectors, foreground wipes, mask-based passes, "
        "time-of-day match cuts, velocity-matched dissolves, invisible cuts in motion blur, radial "
        "match action, and audio-triggered motion. Adapt every transition to EstateReelMaker's calm, "
        "seamless, commercial real-estate style:\n"
        f"{reference}"
    )


@lru_cache(maxsize=1)
def load_video_agent_schema() -> dict[str, Any]:
    try:
        with open(_VIDEO_AGENT_SCHEMA_PATH, encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def video_agent_schema_prompt_text(max_techniques: int = 24) -> str:
    schema = load_video_agent_schema()
    if not schema:
        return ""

    theme_clusters = schema.get("theme_clusters") or {}
    raw_storyboard_rules = schema.get("storyboard_rules") or []
    techniques = schema.get("techniques") or []
    storyboard_rules = (
        raw_storyboard_rules
        if isinstance(raw_storyboard_rules, list)
        else [raw_storyboard_rules]
    )

    analysis_fields: list[str] = []
    analyze_images = schema.get("analyze_images")
    if isinstance(analyze_images, dict):
        per_image = analyze_images.get("per_image_output") or {}
        if isinstance(per_image, dict):
            analysis_fields = list(per_image.keys())[:18]

    technique_lines: list[str] = []
    technique_items = techniques[:max_techniques] if isinstance(techniques, list) else []
    for technique in technique_items:
        if not isinstance(technique, dict):
            continue
        technique_id = technique.get("technique_id") or technique.get("id") or "technique"
        name = technique.get("name") or technique.get("title") or ""
        category = technique.get("category") or technique.get("theme") or ""
        prompt = ""
        fal = technique.get("fal")
        if isinstance(fal, dict):
            prompt = fal.get("prompt") or ""
        prompt = " ".join(str(prompt).split())[:240]
        technique_lines.append(
            " | ".join(str(item) for item in [technique_id, name, category, prompt] if item)
        )

    return (
        "Video agent schema reference from video_agent_schema.json. Use it as a vocabulary for "
        "image analysis, theme grouping, transition technique selection, and render translation; "
        "do not force every rule or blindly copy technique names. Pick only what the actual photos "
        "and their neighbor relationships support. Translate chosen techniques into concrete camera "
        "path, mask, beat, entry-frame, and exit-frame language for FAL and FFmpeg.\n"
        f"Useful image analysis fields: {', '.join(analysis_fields)}\n"
        "Theme clusters: "
        f"{', '.join(str(key) for key in theme_clusters.keys()) if isinstance(theme_clusters, dict) else ''}\n"
        f"Storyboard guardrails: {json.dumps(storyboard_rules[:12], ensure_ascii=True)}\n"
        "Technique vocabulary:\n"
        + "\n".join(technique_lines)
    )


CORE_REEL_SOP = """EstateReelMaker agent standard procedure:
1. Ground every decision in visible user uploads and explicit project/template/music data.
2. Define one binding concept for the whole reel before choosing individual shots.
3. Treat every uploaded photo as a scene in that larger film, not as isolated filler.
4. Give every scene a narrative job: reveal, invitation, proof of scale, material detail, lifestyle breath, emotional turn, or closing memory.
5. Plan motion in milliseconds and beats: beginning pose, camera path, midpoint emphasis, exit frame, and cut reason.
6. Use source-safe masking language for image-to-video: preserve walls, windows, fixtures, furniture, landscaping, reflections, perspective lines, floor plans, text, logos, people, and property identity unless the source clearly supports a change.
7. Use masked motion only where it is safe: light rays, shadows, curtains, fireplace, water, foliage, sky, reflections, subtle foreground parallax, and camera travel. Never warp architecture to create fake drama.
8. Make transitions motivated by geometry, light, direction, room adjacency, visible edges, foreground objects, architectural openings, and audio beats. Do not pick random transitions.
9. Keep the musical grammar calm, commercial, dramatic, refined, and soothing. Avoid trap, hip-hop, hype edits, aggressive impact hits, chaotic whips, or nightclub pacing.
10. If photos are sparse, build a shorter grounded film from the available images. Reuse real images with new camera intention instead of inventing nonexistent rooms.
11. For every shot, inspect its relationship to the previous and next image: camera height, lens feel, entry edge, exit edge, dominant geometry, light direction, foreground/background layers, motion potential, and emotional purpose.
12. For every outgoing pair, choose the natural edit grammar first: handshake, reveal, whip_pan, simple_cut, or match_cut. Write transition_logic with the justification, spatial continuity, technical execution, risk notes, visual distance, inherited velocity, shared anchors, ramp profile, and fallback if a bridge would morph architecture.
13. Be specific enough for a video model and a human editor: camera height, lens feel, focal point, foreground/background behavior, speed ramp, mask holdouts, lighting behavior, transition logic, and emotional purpose.
14. Return structured output only when a schema is requested."""

IMAGE_ANALYSIS_SOP = """Analyze only what is visible. Separate evidence from inference. Capture defects and risks that could break image-to-video, including crooked lines, mirrors, people, readable text, watermarks, clutter, blown windows, harsh flash, blur, and low resolution."""

STORYBOARD_AGENT_SOP = """Storyboard planning standard:
- First write the binding concept: a title, logline, emotional arc, visual theme, music strategy, and continuity rules.
- Then order scenes so the property feels like one coherent mini-film.
- For every scene, write a purpose statement and a shot recipe that covers framing, lens feel, camera path, masked motion zones, holdout zones, transition in/out, beat timing, and what must remain unchanged.
- Design camera perspective as a connected journey across scenes. The camera can rush, decelerate, orbit, pass through a door/window/glass plane, follow a wall edge, match a sky/reflection/material texture, or hide a cut inside foreground motion when the photos support it.
- Be the director. Use first/last-frame bridges only for plausible same-space or adjacent-space handshakes; otherwise use motivated reveals, whip-pans, match-cuts, or clean cuts on the music so the reel stays natural instead of feature-rich.
- Prefer fewer, stronger scenes over filling every template slot when uploads are sparse.
- Never hallucinate a missing room. If a requested room is absent, repurpose the best real image as an honest bridge, detail, exterior, atmosphere, or closing scene."""

FAL_SHOT_SOP = """FAL prompt standard:
Lead with the camera verb first. Keep the provider prompt short, motion-first, and temporal: immediate movement from frame 0, one clear camera path, high fidelity to the source image, calm commercial style, and a simple beat-aware handoff. Put stability failures such as static frame, frozen image, warped geometry, fake architecture, people, logos, and watermarks in the negative prompt instead of overloading the positive prompt."""

TEMPLATE_PROMPT_SOP = """Template authoring standard:
Design reusable templates as editor procedures, not random shot lists. Each slot must have a narrative job, calm commercial movement, practical fallback behavior, and timing that can be beat-synced without forcing hype music-video edits."""
