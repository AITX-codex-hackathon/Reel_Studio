"""Runway Gen-4 — generative motion for hero shots.

Used surgically: only when a slot's `motion` is GENERATIVE. Not part of the
default render path because cost-per-second is non-trivial.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class RunwayClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RUNWAY_API_KEY")
        self.base_url = "https://api.dev.runwayml.com/v1"

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def image_to_video(
        self,
        image_path: Path,
        prompt: str,
        out_path: Path,
        duration_sec: float = 5.0,
        ratio: str = "768:1280",  # 9:16-ish for reels
    ) -> Optional[Path]:
        """Generate a short video clip from a still + motion prompt.

        Returns the output mp4 path on success, None on failure or disabled.
        """
        if not self.enabled:
            log.info("Runway disabled (no RUNWAY_API_KEY) — skipping generative motion")
            return None

        try:
            import httpx  # type: ignore
        except ImportError:
            log.warning("httpx not installed — `pip install httpx`")
            return None

        # Read image, base64-encode for inline submission
        import base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        # Use data URL form
        ext = image_path.suffix.lstrip(".").lower() or "jpg"
        if ext == "jpg":
            ext = "jpeg"
        data_url = f"data:image/{ext};base64,{image_b64}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        }
        payload = {
            "promptImage": data_url,
            "promptText": prompt,
            "model": "gen3a_turbo",
            "duration": min(10, max(5, int(duration_sec))),
            "ratio": ratio,
        }

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                # Submit task
                r = await client.post(
                    f"{self.base_url}/image_to_video",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                task_id = r.json()["id"]

                # Poll
                video_url = None
                for _ in range(120):  # up to 10 minutes
                    await asyncio.sleep(5)
                    r = await client.get(f"{self.base_url}/tasks/{task_id}", headers=headers)
                    r.raise_for_status()
                    body = r.json()
                    status = body.get("status")
                    if status == "SUCCEEDED":
                        video_url = (body.get("output") or [None])[0]
                        break
                    if status in ("FAILED", "CANCELLED"):
                        log.error("Runway task failed: %s", body)
                        return None

                if not video_url:
                    log.warning("Runway task timed out")
                    return None

                # Download
                r = await client.get(video_url)
                r.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                log.info("Runway wrote video to %s", out_path)
                return out_path

        except Exception as e:
            log.exception("Runway request failed: %s", e)
            return None
