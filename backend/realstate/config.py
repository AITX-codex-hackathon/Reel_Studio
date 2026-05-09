"""App settings — env-backed."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./storage_data/realstate.db")
    storage_root: str = os.getenv("STORAGE_ROOT", "./storage_data")
    audio_library_root: str = os.getenv("AUDIO_LIBRARY_ROOT", "./audio_library")
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]

    # VLM provider — "openai" | "claude"
    vlm_provider: str = os.getenv("VLM_PROVIDER", "claude")
    vlm_model: str = os.getenv("VLM_MODEL", "gpt-4o")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Legacy Claude keys (used when vlm_provider=claude)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    claude_vision_model: str = os.getenv("CLAUDE_VISION_MODEL", "claude-sonnet-4-6")

    # Image generation
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    # Image-to-video provider — "fal" | "runway"
    i2v_provider: str = os.getenv("I2V_PROVIDER", "runway")
    fal_api_key: str = os.getenv("FAL_API_KEY", "")
    runway_api_key: str = os.getenv("RUNWAY_API_KEY", "")

    # Audio
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")

    # Pipeline knobs
    quality_threshold: float = float(os.getenv("QUALITY_THRESHOLD", "0.70"))
    min_clip_sec: float = float(os.getenv("MIN_CLIP_SEC", "1.5"))
    max_clip_sec: float = float(os.getenv("MAX_CLIP_SEC", "6.0"))
    max_bad_clips: int = int(os.getenv("MAX_BAD_CLIPS", "10"))
    min_gap_sec: float = float(os.getenv("MIN_GAP_SEC", "5.0"))

    font_path: str | None = os.getenv("FONT_PATH")


@lru_cache
def get_settings() -> Settings:
    return Settings()
