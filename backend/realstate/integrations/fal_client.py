"""FAL image-to-video — drop-in replacement for RunwayClient."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_MODEL = "fal-ai/kling-video/v1.6/standard/image-to-video"


class FalClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FAL_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def image_to_video(
        self,
        image_path: Path,
        prompt: str,
        out_path: Path,
        duration_sec: float = 5.0,
        ratio: str = "768:1280",
    ) -> Optional[Path]:
        if not self.enabled:
            log.info("FAL disabled (no FAL_API_KEY) — skipping generative motion")
            return None

        try:
            import fal_client  # type: ignore
        except ImportError:
            log.warning("fal-client not installed — `pip install fal-client`")
            return None

        try:
            import httpx  # type: ignore
        except ImportError:
            log.warning("httpx not installed — `pip install httpx`")
            return None

        os.environ.setdefault("FAL_KEY", self.api_key)

        with open(image_path, "rb") as f:
            ext = image_path.suffix.lstrip(".").lower() or "jpg"
            if ext == "jpg":
                ext = "jpeg"
            data_url = f"data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"

        duration_str = "5" if duration_sec < 7 else "10"

        try:
            result = await fal_client.run_async(
                _MODEL,
                arguments={
                    "image_url": data_url,
                    "prompt": prompt,
                    "duration": duration_str,
                    "aspect_ratio": "9:16",
                },
            )
        except Exception as e:
            log.exception("FAL i2v failed: %s", e)
            return None

        video_url = (result or {}).get("video", {}).get("url")
        if not video_url:
            log.warning("FAL returned no video URL: %s", result)
            return None

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.get(video_url)
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                log.info("FAL wrote video to %s", out_path)
                return out_path
        except Exception as e:
            log.exception("FAL video download failed: %s", e)
            return None
