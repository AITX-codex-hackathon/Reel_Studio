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

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    runway_api_key: str = os.getenv("RUNWAY_API_KEY", "")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")

    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    claude_vision_model: str = os.getenv("CLAUDE_VISION_MODEL", "claude-sonnet-4-6")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    font_path: str | None = os.getenv("FONT_PATH")  # for drawtext


@lru_cache
def get_settings() -> Settings:
    return Settings()
