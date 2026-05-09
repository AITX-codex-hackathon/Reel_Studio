"""App settings — env-backed."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./storage_data/realstate.db")
    storage_root: str = os.getenv("STORAGE_ROOT", "./storage_data")
    audio_library_root: str = os.getenv("AUDIO_LIBRARY_ROOT", "./audio_library")
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    ]

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    fal_key: str = os.getenv("FAL_KEY", "")
    gemini_api_key: str = _first_env("GEMINI_API_KEY", "GOOGLE_API_KEY")
    runway_api_key: str = os.getenv("RUNWAY_API_KEY", "")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")

    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

    font_path: str | None = os.getenv("FONT_PATH")  # for drawtext


@lru_cache
def get_settings() -> Settings:
    return Settings()
