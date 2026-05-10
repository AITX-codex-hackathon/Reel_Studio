"""Vision-based image analyzer.

This is the grounding layer for storyboard decisions. It deliberately returns
small, stable fields for the matcher, while preserving richer VLM observations
in ``raw`` for debugging and later agent prompts.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .openai_client import OpenAIClient, OpenAIUnavailable
from .prompt_standard import CORE_REEL_SOP, IMAGE_ANALYSIS_SOP

log = logging.getLogger(__name__)

ANALYZER_VERSION = "2026-05-09-robust-v1"

ROOM_TYPES = [
    "exterior", "foyer", "kitchen", "living_room", "bedroom", "bathroom",
    "dining", "backyard", "view", "amenity", "lifestyle", "detail",
]
FRAMINGS = ["wide", "medium", "close", "detail"]
LIGHTING = ["bright", "soft", "golden_hour", "low_light", "harsh"]
MOTIONS = [
    "static", "slow_zoom_in", "slow_zoom_out", "push_in", "pull_out",
    "pan_left", "pan_right", "pan_up", "pan_down",
]

_ROOM_ALIASES = {
    "aerial": "exterior",
    "balcony": "view",
    "bath": "bathroom",
    "bath room": "bathroom",
    "deck": "backyard",
    "dining room": "dining",
    "drone": "exterior",
    "driveway": "exterior",
    "entry": "foyer",
    "entryway": "foyer",
    "front": "exterior",
    "front exterior": "exterior",
    "garage": "amenity",
    "garden": "backyard",
    "great room": "living_room",
    "hall": "foyer",
    "hallway": "foyer",
    "laundry": "amenity",
    "living": "living_room",
    "living room": "living_room",
    "lounge": "living_room",
    "office": "amenity",
    "patio": "backyard",
    "pool": "backyard",
    "powder room": "bathroom",
    "primary suite": "bedroom",
    "rear": "backyard",
    "terrace": "backyard",
    "yard": "backyard",
}

_FILENAME_ROOM_HINTS = {
    "exterior": ("exterior", "front", "facade", "driveway", "aerial", "drone", "street", "elevation"),
    "foyer": ("foyer", "entry", "entryway", "hall", "hallway", "stairs", "staircase"),
    "kitchen": ("kitchen", "island", "pantry", "cabinet", "countertop"),
    "living_room": ("living", "greatroom", "great_room", "family", "lounge"),
    "bedroom": ("bed", "bedroom", "primary", "suite", "master"),
    "bathroom": ("bath", "bathroom", "powder", "vanity", "shower", "tub"),
    "dining": ("dining", "breakfast", "eat-in"),
    "backyard": ("backyard", "yard", "patio", "deck", "terrace", "pool", "garden", "rear"),
    "view": ("view", "balcony", "window", "city", "ocean", "mountain", "skyline"),
    "amenity": ("office", "laundry", "garage", "gym", "theater", "media", "wine", "mudroom"),
    "detail": ("detail", "close", "fixture", "hardware", "fireplace", "tile", "texture"),
}

_SYSTEM = (
    "You are the visual intelligence layer for a premium AI real-estate reel editor. "
    "Analyze the actual uploaded listing photo only. Be precise and conservative: do not "
    "invent unseen rooms, luxury features, views, pools, or furniture. Return exactly one "
    "valid JSON object and no prose.\n\n"
    f"{CORE_REEL_SOP}\n\n{IMAGE_ANALYSIS_SOP}"
)

_USER_TEMPLATE = """Analyze this real-estate listing photo for a cinematic reel planner.

Return exactly one JSON object with this schema:
{{
  "room_type": one of {rooms},
  "secondary_room_types": [zero to three values from {rooms}],
  "confidence": 0.0 to 1.0,
  "quality_score": 0.0 to 1.0,
  "framing": "wide" | "medium" | "close" | "detail",
  "lighting": "bright" | "soft" | "golden_hour" | "low_light" | "harsh",
  "dominant_colors": ["color name", ... up to 3],
  "suggested_motion": one of {motions},
  "usable_as": ["hero" | "bridge" | "detail" | "closing" | "context"],
  "cinematic_strengths": ["specific visual strength", ... up to 4],
  "defects": ["specific defect or risk", ... up to 4],
  "notes": "one concise, grounded sentence describing what is visible"
}}

Rules:
- If uncertain between room labels, pick the safest visible category and put alternatives in secondary_room_types.
- Use "view" only when the view itself is the subject. Use "backyard" for patios, pools, gardens, decks, or rear exteriors.
- Use "detail" only for close-ups of fixtures/materials/details, not just because the room is unknown.
- Use "lifestyle" only for staging/detail photos intended to sell mood rather than a room.
- Penalize quality_score for blur, compression, low resolution, dark exposure, harsh flash, clutter, crooked lines, reflections, or visible people.
- suggested_motion must be calm commercial real-estate motion, not hype/action movement.
- Notes and cinematic_strengths must be useful to a later storyboard director deciding scene purpose, camera path, masking risk, and transition continuity.
"""


@dataclass
class ImageAnalysisResult:
    room_type: str
    quality_score: float
    framing: str
    lighting: str
    dominant_colors: list[str]
    suggested_motion: str
    notes: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImageAnalyzer:
    def __init__(self, llm: Optional[OpenAIClient] = None):
        self.llm = llm or OpenAIClient()

    async def analyze(self, image_path: Path) -> ImageAnalysisResult:
        fallback = self._heuristic(image_path)
        if self.llm.enabled:
            try:
                return await self._analyze_with_llm(image_path, fallback=fallback)
            except OpenAIUnavailable:
                pass
            except Exception as error:
                log.warning("Vision analysis failed, falling back: %s", error)
        return fallback

    async def _analyze_with_llm(self, image_path: Path, fallback: ImageAnalysisResult) -> ImageAnalysisResult:
        user_text = _USER_TEMPLATE.format(rooms=ROOM_TYPES, motions=MOTIONS)
        last_error = ""

        for attempt in range(2):
            prompt = user_text
            if last_error:
                prompt += (
                    "\n\nYour previous response could not be parsed or validated. "
                    f"Validation error: {last_error}. Return corrected JSON only."
                )
            try:
                text = await self.llm.vision(
                    system=_SYSTEM,
                    user_text=prompt,
                    image_path=image_path,
                    max_tokens=900,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
            except Exception as json_mode_error:
                log.info("Vision JSON mode unavailable; retrying plain vision: %s", json_mode_error)
                text = await self.llm.vision(
                    system=_SYSTEM,
                    user_text=prompt,
                    image_path=image_path,
                    max_tokens=900,
                    temperature=0.1,
                )

            try:
                data = _extract_json_object(text)
                return _normalize_analysis(data, image_path=image_path, fallback=fallback)
            except Exception as error:
                last_error = str(error)

        raise ValueError(f"Vision model returned invalid analysis: {last_error}")

    def _heuristic(self, image_path: Path) -> ImageAnalysisResult:
        """No-API fallback. Uses filename and image dimensions/brightness when available."""
        name = _tokenize_name(image_path)
        room = _room_from_text(name) or "detail"

        width = height = 0
        brightness = None
        dominant_colors: list[str] = []
        quality = 0.52
        try:
            from PIL import Image, ImageStat  # type: ignore

            with Image.open(image_path) as im:
                width, height = im.size
                rgb = im.convert("RGB").resize((1, 1))
                r, g, b = rgb.getpixel((0, 0))
                brightness = (r + g + b) / 3
                dominant_colors = [_rough_color_name(r, g, b)]
                gray = im.convert("L").resize((64, 64))
                stat = ImageStat.Stat(gray)
                contrast = stat.stddev[0]
                quality = 0.48 + min(width, height) / 4000 + min(contrast, 64) / 400
        except Exception:
            pass
        quality = _clamp_float(quality, 0.25, 0.78)

        framing = _framing_from_name_or_size(name, width, height)
        lighting = _lighting_from_name_or_brightness(name, brightness)
        motion = _motion_for(room, framing, width, height)
        return ImageAnalysisResult(
            room_type=room,
            quality_score=quality,
            framing=framing,
            lighting=lighting,
            dominant_colors=dominant_colors[:3],
            suggested_motion=motion,
            notes=f"Heuristic analysis from filename/image metadata; likely {room.replace('_', ' ')}.",
            raw={
                "source": "heuristic",
                "analyzer_version": ANALYZER_VERSION,
                "confidence": 0.35 if room == "detail" else 0.5,
                "secondary_room_types": [],
                "usable_as": _usable_as(room, framing),
                "image": {"width": width, "height": height, "brightness": brightness},
            },
        )


def _normalize_analysis(
    data: dict[str, Any],
    image_path: Path,
    fallback: ImageAnalysisResult,
) -> ImageAnalysisResult:
    image_meta = _image_meta(image_path)
    room = _normalize_room(data.get("room_type")) or fallback.room_type
    secondary = [
        normalized
        for item in _as_list(data.get("secondary_room_types"))
        if (normalized := _normalize_room(item)) and normalized != room
    ][:3]
    if fallback.room_type != room and fallback.room_type != "detail" and fallback.room_type not in secondary:
        secondary.append(fallback.room_type)

    framing = _normalize_framing(data.get("framing")) or fallback.framing
    lighting = _normalize_lighting(data.get("lighting")) or fallback.lighting
    quality = _coerce_float(data.get("quality_score"), fallback.quality_score)
    confidence = _clamp_float(_coerce_float(data.get("confidence"), 0.65), 0.0, 1.0)
    if image_meta["min_side"] and image_meta["min_side"] < 800:
        quality -= 0.15
    if data.get("defects"):
        quality -= min(0.16, 0.04 * len(_as_list(data.get("defects"))))
    quality = _clamp_float(quality, 0.1, 1.0)

    colors = [_clean_color(color) for color in _as_list(data.get("dominant_colors"))]
    colors = [color for color in colors if color][:3] or fallback.dominant_colors
    motion = _normalize_motion(data.get("suggested_motion")) or _motion_for(room, framing, image_meta["width"], image_meta["height"])
    notes = str(data.get("notes") or fallback.notes).strip()
    if not notes:
        notes = f"Visible real-estate image analyzed as {room.replace('_', ' ')}."

    raw = dict(data)
    raw.update(
        {
            "source": "openai_vision",
            "analyzer_version": ANALYZER_VERSION,
            "confidence": confidence,
            "secondary_room_types": secondary,
            "usable_as": _normalize_usable_as(data.get("usable_as"), room, framing),
            "cinematic_strengths": [str(item).strip() for item in _as_list(data.get("cinematic_strengths")) if str(item).strip()][:4],
            "defects": [str(item).strip() for item in _as_list(data.get("defects")) if str(item).strip()][:4],
            "image": image_meta,
        }
    )
    return ImageAnalysisResult(
        room_type=room,
        quality_score=quality,
        framing=framing,
        lighting=lighting,
        dominant_colors=colors,
        suggested_motion=motion,
        notes=notes[:500],
        raw=raw,
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("\ufeff").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    decoder = json.JSONDecoder()
    for idx, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(cleaned[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON object found in vision response")


def _normalize_room(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_")
    text = re.sub(r"\s+", " ", text).replace(" ", "_")
    if text in ROOM_TYPES:
        return text
    alias_key = text.replace("_", " ")
    if alias_key in _ROOM_ALIASES:
        return _ROOM_ALIASES[alias_key]
    return _room_from_text(text)


def _room_from_text(text: str) -> Optional[str]:
    normalized = text.lower().replace("-", "_")
    compact = normalized.replace("_", "")
    for room, hints in _FILENAME_ROOM_HINTS.items():
        if any(hint in normalized or hint.replace("_", "") in compact for hint in hints):
            return room
    for alias, room in _ROOM_ALIASES.items():
        if alias in normalized.replace("_", " "):
            return room
    return None


def _normalize_framing(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text in FRAMINGS:
        return text
    if any(term in text for term in ("aerial", "drone", "establishing", "ultra_wide", "wide")):
        return "wide"
    if any(term in text for term in ("macro", "fixture", "material", "detail")):
        return "detail"
    if any(term in text for term in ("close", "tight")):
        return "close"
    if any(term in text for term in ("medium", "mid")):
        return "medium"
    return None


def _normalize_lighting(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text in LIGHTING:
        return text
    if any(term in text for term in ("gold", "sunset", "sunrise", "twilight", "blue_hour")):
        return "golden_hour"
    if any(term in text for term in ("dark", "dim", "night", "underexposed")):
        return "low_light"
    if any(term in text for term in ("flash", "blown", "overexposed", "hard")):
        return "harsh"
    if any(term in text for term in ("natural", "diffuse", "soft")):
        return "soft"
    if any(term in text for term in ("bright", "day", "daylight")):
        return "bright"
    return None


def _normalize_motion(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text in MOTIONS:
        return text
    if "push" in text or "zoom_in" in text:
        return "slow_zoom_in"
    if "pull" in text or "zoom_out" in text:
        return "slow_zoom_out"
    if "left" in text:
        return "pan_left"
    if "right" in text:
        return "pan_right"
    if "up" in text or "tilt_up" in text:
        return "pan_up"
    if "down" in text or "tilt_down" in text:
        return "pan_down"
    return None


def _motion_for(room: str, framing: str, width: int = 0, height: int = 0) -> str:
    if height > width * 1.25:
        return "pan_up" if room in {"exterior", "foyer"} else "slow_zoom_in"
    if framing in {"detail", "close"}:
        return "slow_zoom_in"
    if room in {"exterior", "backyard", "view"}:
        return "slow_zoom_out"
    if room in {"kitchen", "living_room", "dining"}:
        return "pan_right"
    return "slow_zoom_in"


def _normalize_usable_as(value: Any, room: str, framing: str) -> list[str]:
    allowed = {"hero", "bridge", "detail", "closing", "context"}
    items = [str(item).strip().lower() for item in _as_list(value)]
    usable = [item for item in items if item in allowed]
    if usable:
        return usable[:4]
    return _usable_as(room, framing)


def _usable_as(room: str, framing: str) -> list[str]:
    if framing in {"detail", "close"} or room == "detail":
        return ["detail", "bridge"]
    if room in {"exterior", "view", "backyard"}:
        return ["hero", "closing", "context"]
    return ["bridge", "context"]


def _framing_from_name_or_size(name: str, width: int, height: int) -> str:
    if any(k in name for k in ("aerial", "drone", "wide", "exterior", "hero")):
        return "wide"
    if any(k in name for k in ("close", "detail", "macro", "fixture", "tile")):
        return "detail"
    if width and height:
        ratio = max(width, height) / max(1, min(width, height))
        if ratio > 1.65:
            return "wide"
    return "medium"


def _lighting_from_name_or_brightness(name: str, brightness: Optional[float]) -> str:
    if any(k in name for k in ("sunset", "sunrise", "golden", "twilight")):
        return "golden_hour"
    if any(k in name for k in ("night", "dark", "lowlight", "low_light")):
        return "low_light"
    if brightness is None:
        return "bright"
    if brightness < 70:
        return "low_light"
    if brightness > 220:
        return "harsh"
    if 120 <= brightness <= 190:
        return "soft"
    return "bright"


def _image_meta(image_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as image:
            width, height = image.size
        return {"width": width, "height": height, "min_side": min(width, height)}
    except Exception:
        return {"width": 0, "height": 0, "min_side": 0}


def _rough_color_name(r: int, g: int, b: int) -> str:
    if max(r, g, b) < 45:
        return "black"
    if min(r, g, b) > 215:
        return "white"
    if abs(r - g) < 16 and abs(g - b) < 16:
        return "gray"
    if r > g and r > b:
        return "warm beige" if g > b else "red brown"
    if g > r and g > b:
        return "green"
    if b > r and b > g:
        return "blue gray"
    return "neutral"


def _clean_color(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9 /_-]", "", text)[:40]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        if "," in value:
            return [part.strip() for part in value.split(",")]
        return [value]
    return [value]


def _coerce_float(value: Any, default: float) -> float:
    try:
        if isinstance(value, str) and value.strip().endswith("%"):
            return float(value.strip().rstrip("%")) / 100
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _tokenize_name(image_path: Path) -> str:
    return re.sub(r"[^a-z0-9_ -]", " ", image_path.stem.lower())
