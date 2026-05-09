"""fal.ai image generation and editing for missing real-estate shots."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


class FalImageClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        edit_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
        self.model = model or os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/dev")
        self.edit_model = edit_model or os.getenv("FAL_IMAGE_EDIT_MODEL", "fal-ai/flux-pro/kontext")

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
        """Generate or edit an image using fal.ai and write it to disk."""
        if not self.enabled:
            log.info("fal image generation disabled (no FAL_KEY/FAL_API_KEY)")
            return None

        try:
            import fal_client  # type: ignore
        except ImportError:
            log.warning("fal-client not installed — `pip install fal-client`")
            return None

        previous_key = os.environ.get("FAL_KEY")
        os.environ["FAL_KEY"] = self.api_key or ""
        try:
            arguments = await self._build_arguments(fal_client, prompt, reference_images, aspect_ratio)
            endpoint = self.edit_model if reference_images else self.model
            result = await asyncio.to_thread(_run_fal, fal_client, endpoint, arguments)
            image_url = _extract_image_url(result)
            if not image_url:
                log.warning("fal returned no image URL for endpoint %s", endpoint)
                return None
            await _download(image_url, out_path)
            log.info("fal wrote image to %s", out_path)
            return out_path
        except Exception as error:
            log.exception("fal image generation failed: %s", error)
            return None
        finally:
            if previous_key is None:
                os.environ.pop("FAL_KEY", None)
            else:
                os.environ["FAL_KEY"] = previous_key

    async def _build_arguments(
        self,
        fal_client: Any,
        prompt: str,
        reference_images: Optional[list[Path]],
        aspect_ratio: str,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpeg",
        }
        if reference_images:
            image_url = await asyncio.to_thread(fal_client.upload_file, str(reference_images[0]))
            arguments["image_url"] = image_url
            arguments["strength"] = 0.68
        return arguments


def _run_fal(fal_client: Any, endpoint: str, arguments: dict[str, Any]) -> Any:
    handler = fal_client.submit(endpoint, arguments=arguments)
    return handler.get()


async def _download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        out_path.write_bytes(response.content)


def _extract_image_url(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        images = result.get("images") or []
        for image in images:
            if isinstance(image, dict) and isinstance(image.get("url"), str):
                return image["url"]
        if isinstance(result.get("image"), dict) and isinstance(result["image"].get("url"), str):
            return result["image"]["url"]
        if isinstance(result.get("url"), str):
            return result["url"]
    return None
