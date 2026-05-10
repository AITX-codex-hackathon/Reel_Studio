"""VideoStyle — a cinematic shot style from the style catalog."""
from __future__ import annotations

from pydantic import BaseModel


CATEGORIES = [
    "Drone Aerial",
    "Dolly Interior",
    "Dolly Exterior",
    "Sunset/Twilight",
    "Lighting Logic",
    "Macro/Detail",
    "High-Energy",
    "Seamless Bridge",
]


class VideoStyle(BaseModel):
    style_id: str               # e.g. "VID_DRN_001"
    category: str               # e.g. "Drone Aerial"
    mood: str                   # e.g. "Epic/Grand"
    camera_motion: str          # e.g. "High-Altitude Orbit"
    environmental_dynamics: str # e.g. "Cloud shadow drift"
    video_prompt: str           # full cinematic prompt for i2v model
