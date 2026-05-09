"""Nano Banana Pro — Google Gemini image generation.

Used for:
  - generating missing shots (e.g. "sunset exterior" when only daytime uploads exist)
  - smart cropping / reframing existing uploads to a target aspect ratio
  - image enhancement (relight, denoise, upscale-ish)
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class NanoBananaClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3-pro-image-preview"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = os.getenv("GEMINI_IMAGE_MODEL", model)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        prompt: str,
        out_path: Path,
        reference_images: Optional[list[Path]] = None,
        aspect_ratio: str = "9:16",
    ) -> Optional[Path]:
        """Generate (or edit) an image from `prompt`.

        Returns the output path on success, None on failure or if disabled.
        """
        if not self.enabled:
            log.info("Nano Banana disabled (no GEMINI_API_KEY) — skipping generation for: %s", prompt[:60])
            return None

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError:
            log.warning("google-genai not installed — `pip install google-genai`")
            return None

        client = genai.Client(api_key=self.api_key)

        contents: list = [prompt]
        if reference_images:
            for ref in reference_images:
                with open(ref, "rb") as f:
                    contents.append(
                        types.Part.from_bytes(
                            data=f.read(),
                            mime_type="image/jpeg" if str(ref).lower().endswith(".jpg") else "image/png",
                        )
                    )

        try:
            response = await _run_async(
                lambda: client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    ),
                )
            )
        except Exception as e:
            log.exception("Nano Banana generation failed: %s", e)
            return None

        # Walk response parts looking for inline image data
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    raw = part.inline_data.data
                    if isinstance(raw, str):
                        raw = base64.b64decode(raw)
                    with open(out_path, "wb") as f:
                        f.write(raw)
                    log.info("Nano Banana wrote image to %s", out_path)
                    return out_path

        log.warning("Nano Banana returned no image data for prompt: %s", prompt[:60])
        return None

    async def smart_crop(
        self,
        source: Path,
        out_path: Path,
        aspect_ratio: str = "9:16",
        intent: str = "preserve the main subject and architectural composition",
    ) -> Optional[Path]:
        """Reframe an image for a target aspect ratio without losing the subject."""
        prompt = (
            f"Reframe this real-estate photo to a {aspect_ratio} aspect ratio. "
            f"{intent}. Do not add or invent new content; only crop and gently extend "
            f"matching edges if absolutely necessary. Keep the original style and lighting."
        )
        return await self.generate(prompt, out_path, reference_images=[source], aspect_ratio=aspect_ratio)


async def _run_async(fn):
    """Run a sync function in a thread so we don't block the event loop."""
    import asyncio
    return await asyncio.to_thread(fn)
