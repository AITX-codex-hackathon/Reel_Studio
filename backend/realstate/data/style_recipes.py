"""Load styleRecipe.txt and map room types to cinematic FAL prompts."""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_RECIPE_FILE = Path(__file__).resolve().parents[3] / "styleRecipe.txt"

# House-tour shot ordering priority
ROOM_ORDER: dict[str, int] = {
    "exterior": 0,
    "view": 1,
    "foyer": 2,
    "living_room": 3,
    "dining": 4,
    "kitchen": 5,
    "bedroom": 6,
    "bathroom": 7,
    "backyard": 8,
    "pool": 8,
    "amenity": 9,
    "lifestyle": 10,
    "detail": 11,
}

# Room type → best-fit recipe category
ROOM_TO_CATEGORY: dict[str, str] = {
    "exterior": "Drone Aerial",
    "view": "Drone Aerial",
    "foyer": "Dolly Interior",
    "living_room": "Dolly Interior",
    "kitchen": "Dolly Interior",
    "dining": "Dolly Interior",
    "bedroom": "Dolly Interior",
    "bathroom": "Macro/Detail",
    "backyard": "Sunset/Twilight",
    "pool": "Sunset/Twilight",
    "amenity": "Dolly Interior",
    "lifestyle": "Dolly Interior",
    "detail": "Macro/Detail",
}

_DEFAULT_CATEGORY = "Dolly Interior"
_AVOID_STYLE_TERMS = (
    "aggressive",
    "action",
    "fast",
    "fpv",
    "high-energy",
    "rapid",
    "whip",
    "dive",
    "intense",
)
_PREFERRED_STYLE_TERMS = (
    "architectural",
    "calm",
    "cinematic",
    "establishing",
    "golden",
    "high-end",
    "luxury",
    "modern",
    "moody",
    "smooth",
    "symmetrical",
    "twilight",
)


@dataclass
class StyleRecipe:
    style_id: str
    category: str
    mood: str
    camera_motion: str
    environmental_dynamics: str
    video_prompt: str


_cache: Optional[list[StyleRecipe]] = None


def _load_all() -> list[StyleRecipe]:
    global _cache
    if _cache is not None:
        return _cache
    recipes: list[StyleRecipe] = []
    try:
        with open(_RECIPE_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                recipes.append(StyleRecipe(
                    style_id=row["Style_ID"],
                    category=row["Category"],
                    mood=row["Mood"],
                    camera_motion=row["Camera_Motion"],
                    environmental_dynamics=row["Environmental_Dynamics"],
                    video_prompt=row["Video_Prompt"],
                ))
    except Exception:
        pass
    _cache = recipes
    return recipes


def by_category(category: str) -> list[StyleRecipe]:
    return [r for r in _load_all() if r.category == category]


def get_for_room(room_type: Optional[str], seed: Optional[int] = None) -> Optional[StyleRecipe]:
    category = ROOM_TO_CATEGORY.get(room_type or "", _DEFAULT_CATEGORY)
    pool = by_category(category) or _load_all()
    if not pool:
        return None
    return random.Random(seed).choice(pool)


def get_cinematic_for_room(room_type: Optional[str], seed: Optional[int] = None) -> Optional[StyleRecipe]:
    """Pick a calm commercial recipe, avoiding hype/action-heavy camera language."""
    category = ROOM_TO_CATEGORY.get(room_type or "", _DEFAULT_CATEGORY)
    pool = by_category(category) or _load_all()
    if not pool:
        return None

    filtered = [recipe for recipe in pool if not _has_any(recipe, _AVOID_STYLE_TERMS)]
    preferred = [recipe for recipe in filtered if _has_any(recipe, _PREFERRED_STYLE_TERMS)]
    final_pool = preferred or filtered or pool
    return random.Random(seed).choice(final_pool)


def get_by_id(style_id: str) -> Optional[StyleRecipe]:
    return next((r for r in _load_all() if r.style_id == style_id), None)


def _has_any(recipe: StyleRecipe, terms: tuple[str, ...]) -> bool:
    text = " ".join(
        [
            recipe.category,
            recipe.mood,
            recipe.camera_motion,
            recipe.environmental_dynamics,
            recipe.video_prompt,
        ]
    ).lower()
    return any(term in text for term in terms)
