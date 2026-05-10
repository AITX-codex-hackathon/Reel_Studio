"""ElevenLabs adapter — TTS voiceover and music generation."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class ElevenLabsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def tts(
        self,
        text: str,
        out_path: Path,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # default "Rachel"
        model_id: str = "eleven_multilingual_v2",
    ) -> Optional[Path]:
        if not self.enabled:
            return None

        try:
            import httpx  # type: ignore
        except ImportError:
            log.warning("httpx not installed")
            return None

        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.30},
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                return out_path
        except Exception as e:
            log.exception("ElevenLabs TTS failed: %s", e)
            return None

    async def music(
        self,
        prompt: str,
        out_path: Path,
        duration_sec: float = 60.0,
    ) -> Optional[Path]:
        """Generate background music from a text prompt.

        Uses ElevenLabs Music endpoint (released 2025).
        """
        if not self.enabled:
            return None

        try:
            import httpx  # type: ignore
        except ImportError:
            return None

        url = f"{self.base_url}/music"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "music_length_ms": int(duration_sec * 1000),
        }
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                return out_path
        except Exception as e:
            log.exception("ElevenLabs music gen failed: %s", e)
            return None
