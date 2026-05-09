"""Vision-based image analyzer.

For each upload, returns:
  - room_type
  - quality_score (0..1)
  - framing (wide / medium / close / detail)
  - lighting (bright / soft / golden_hour / low_light / harsh)
  - dominant_colors
  - suggested_motion
  - notes

When OpenAI is unavailable, falls back to deterministic heuristics based on
filename and (if PIL is available) image dimensions / brightness.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .openai_client import OpenAIClient, OpenAIUnavailable

log = logging.getLogger(__name__)

ROOM_TYPES = [
    "exterior", "foyer", "kitchen", "living_room", "bedroom", "bathroom",
    "dining", "backyard", "view", "amenity", "lifestyle", "detail",
]
MOTIONS = [
    "static", "slow_zoom_in", "slow_zoom_out", "push_in", "pull_out",
    "pan_left", "pan_right", "pan_up", "pan_down",
]


@dataclass
class ImageAnalysisResult:
    room_type: str
    quality_score: float
    framing: str
    lighting: str
    dominant_colors: list[str]
    suggested_motion: str
    notes: str
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_SYSTEM = (
    "You are a real estate video editor's assistant. You analyze listing photos to decide "
    "how each one should be used in a short cinematic reel. You answer ONLY with a single JSON "
    "object — no prose, no markdown fences, no code blocks."
)

_USER_TEMPLATE = """Analyze this real estate photo. Respond with EXACTLY this JSON shape:

{{
  "room_type": one of {rooms},
  "quality_score": 0.0 to 1.0 (composition + sharpness + lighting + appeal),
  "framing": "wide" | "medium" | "close" | "detail",
  "lighting": "bright" | "soft" | "golden_hour" | "low_light" | "harsh",
  "dominant_colors": ["color name", ...] (up to 3),
  "suggested_motion": one of {motions},
  "notes": one sentence describing what's in the shot and any defects to avoid
}}

Be conservative on quality_score — penalize: blurry, dark, cluttered, awkward angles,
visible photographer/reflection, time-stamped photos, low resolution.
"""


class ImageAnalyzer:
    def __init__(self, claude: Optional[ClaudeClient] = None):
        self.claude = claude or ClaudeClient()

    async def analyze(self, image_path: Path) -> ImageAnalysisResult:
        if self.llm.enabled:
            try:
                return await self._analyze_with_llm(image_path)
            except OpenAIUnavailable:
                pass
            except Exception as e:
                log.warning("Vision analysis failed, falling back: %s", e)
        return self._heuristic(image_path)

    async def _analyze_with_llm(self, image_path: Path) -> ImageAnalysisResult:
        text = await self.llm.vision(
            system=_SYSTEM,
            user_text=_USER_TEMPLATE.format(rooms=ROOM_TYPES, motions=MOTIONS),
            image_path=image_path,
            max_tokens=512,
        )
        # Extract JSON (defend against accidental code fences)
        json_text = _extract_json(text)
        data = json.loads(json_text)
        return ImageAnalysisResult(
            room_type=_clamp(data.get("room_type", "detail"), ROOM_TYPES, default="detail"),
            quality_score=float(max(0.0, min(1.0, data.get("quality_score", 0.5)))),
            framing=str(data.get("framing", "medium")),
            lighting=str(data.get("lighting", "bright")),
            dominant_colors=list(data.get("dominant_colors", []))[:3],
            suggested_motion=_clamp(data.get("suggested_motion", "static"), MOTIONS, default="static"),
            notes=str(data.get("notes", "")),
            raw=data,
        )

    def _heuristic(self, image_path: Path) -> ImageAnalysisResult:
        """No-API fallback. Guesses room from filename, neutral defaults otherwise."""
        name = image_path.stem.lower()
        room = "detail"
        for r in ROOM_TYPES:
            if r in name or r.replace("_", " ") in name or r.replace("_", "") in name:
                room = r
                break

        # Cheap framing guess from name
        framing = "medium"
        if any(k in name for k in ("wide", "exterior", "drone", "aerial")):
            framing = "wide"
        elif any(k in name for k in ("close", "detail", "macro")):
            framing = "close"

        # Quality from PIL if available
        quality = 0.5
        try:
            from PIL import Image  # type: ignore
            with Image.open(image_path) as im:
                w, h = im.size
                if min(w, h) >= 1500:
                    quality = 0.65
                if min(w, h) < 800:
                    quality = 0.35
        except Exception:
            pass

        motion = "slow_zoom_in" if framing == "wide" else "static"
        return ImageAnalysisResult(
            room_type=room,
            quality_score=quality,
            framing=framing,
            lighting="bright",
            dominant_colors=[],
            suggested_motion=motion,
            notes="Heuristic analysis (no vision model available)",
            raw={"source": "heuristic"},
        )


def _clamp(value, allowed, default):
    return value if value in allowed else default


def _extract_json(text: str) -> str:
    """Pull a JSON object out of model output, even if wrapped in fences."""
    # Try fenced code block first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Greedy: grab first {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0)
    return text.strip()
