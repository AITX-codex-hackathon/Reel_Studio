"""FAL image-to-video and text-to-video via Kling v1.6."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_I2V_MODEL = "fal-ai/kling-video/v1.6/standard/image-to-video"
_T2V_MODEL = "fal-ai/kling-video/v1.6/standard/text-to-video"
_MAX_PROMPT_CHARS = 2400


class FalClient:
    def __init__(self, api_key: Optional[str] = None):
        # Accept both FAL_API_KEY (our config) and FAL_KEY (fal-client library convention)
        self.api_key = api_key or os.getenv("FAL_API_KEY") or os.getenv("FAL_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _setup_env(self) -> None:
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key

    async def image_to_video(
        self,
        image_path: Path,
        prompt: str,
        out_path: Path,
        duration_sec: float = 5.0,
        ratio: str = "9:16",
    ) -> Optional[Path]:
        if not self.enabled:
            log.info("FAL disabled — no API key")
            return None

        try:
            import fal_client  # type: ignore
        except ImportError:
            log.warning("fal-client not installed")
            return None

        self._setup_env()

        with open(image_path, "rb") as f:
            ext = image_path.suffix.lstrip(".").lower() or "jpeg"
            if ext == "jpg":
                ext = "jpeg"
            data_url = f"data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"

        try:
            prompt = _limit_prompt(prompt)
            result = await fal_client.run_async(
                _I2V_MODEL,
                arguments={
                    "image_url": data_url,
                    "prompt": prompt,
                    "duration": "5",
                    "aspect_ratio": ratio,
                },
            )
        except Exception as e:
            log.exception("FAL i2v failed: %s", e)
            return None

        return await self._download(result, out_path)

    async def text_to_video(
        self,
        prompt: str,
        out_path: Path,
        ratio: str = "9:16",
    ) -> Optional[Path]:
        """Generate a 5s clip from prompt alone — used when no source image is available."""
        if not self.enabled:
            log.info("FAL disabled — no API key")
            return None

        try:
            import fal_client  # type: ignore
        except ImportError:
            log.warning("fal-client not installed")
            return None

        self._setup_env()

        try:
            prompt = _limit_prompt(prompt)
            result = await fal_client.run_async(
                _T2V_MODEL,
                arguments={
                    "prompt": prompt,
                    "duration": "5",
                    "aspect_ratio": ratio,
                },
            )
        except Exception as e:
            log.exception("FAL t2v failed: %s", e)
            return None

        return await self._download(result, out_path)

    async def _download(self, result: dict, out_path: Path) -> Optional[Path]:
        try:
            import httpx  # type: ignore
        except ImportError:
            log.warning("httpx not installed")
            return None

        video_url = (result or {}).get("video", {}).get("url")
        if not video_url:
            log.warning("FAL returned no video URL: %s", result)
            return None

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                r = await client.get(video_url)
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                log.info("FAL wrote clip → %s", out_path)
                return out_path
        except Exception as e:
            log.exception("FAL download failed: %s", e)
            return None


def _limit_prompt(prompt: str) -> str:
    cleaned = " ".join((prompt or "").split()).strip()
    if len(cleaned) <= _MAX_PROMPT_CHARS:
        return cleaned
    log.warning("FAL prompt exceeded %d chars; compacting provider prompt.", _MAX_PROMPT_CHARS)
    keep_tail = (
        " Preserve source image geometry, room identity, materials, fixtures, text, people, logos, "
        "and architecture. No fake rooms, no warped walls, no chaotic whip moves, no aggressive edit."
    )
    available = _MAX_PROMPT_CHARS - len(keep_tail) - 1
    return f"{cleaned[:available].rstrip()} {keep_tail}".strip()
