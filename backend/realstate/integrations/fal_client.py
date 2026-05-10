"""FAL image-to-video, first/last-frame transitions, and text-to-video."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_I2V_MODEL = "fal-ai/kling-video/v1.6/standard/image-to-video"
_T2V_MODEL = "fal-ai/kling-video/v1.6/standard/text-to-video"
_FLFV_MODEL = "fal-ai/kling-video/o1/standard/image-to-video"
try:
    _MAX_PROMPT_CHARS = int(os.getenv("FAL_MAX_PROMPT_CHARS", "1200"))
except ValueError:
    _MAX_PROMPT_CHARS = 1200
_NEGATIVE_PROMPT = (
    "static, frozen frame, still image, locked-off shot, motionless, no camera movement, "
    "slideshow, jitter, stutter, blurry, warped geometry, melting walls, distorted fixtures, "
    "fake architecture, extra rooms, added people, text changes, logos, watermark, aggressive hype edit"
)


class FalClient:
    def __init__(self, api_key: Optional[str] = None):
        # Accept both FAL_API_KEY (our config) and FAL_KEY (fal-client library convention)
        self.api_key = api_key or os.getenv("FAL_API_KEY") or os.getenv("FAL_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def transition_bridges_enabled(self) -> bool:
        value = os.getenv("FAL_TRANSITION_BRIDGES", "0").strip().lower()
        return self.enabled and value not in {"0", "false", "no", "off"}

    @property
    def transition_duration_sec(self) -> float:
        try:
            return max(3.0, min(10.0, float(os.getenv("FAL_TRANSITION_DURATION_SEC", "3"))))
        except ValueError:
            return 3.0

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

        data_url = _image_data_url(image_path)

        try:
            prompt = _limit_prompt(prompt)
            arguments = _with_negative_prompt({
                "image_url": data_url,
                "prompt": prompt,
                "duration": _scene_duration_value(duration_sec),
                "aspect_ratio": ratio,
            })
            result = await fal_client.run_async(
                _I2V_MODEL,
                arguments=arguments,
            )
        except Exception as e:
            result = await _retry_without_negative_prompt(
                fal_client=fal_client,
                model=_I2V_MODEL,
                arguments=arguments if "arguments" in locals() else {},
                error=e,
                label="FAL i2v",
            )
            if result is None:
                return None

        return await self._download(result, out_path)

    async def first_last_frame_to_video(
        self,
        start_image_path: Path,
        end_image_path: Path,
        prompt: str,
        out_path: Path,
        duration_sec: Optional[float] = None,
    ) -> Optional[Path]:
        """Generate a true transition clip anchored by first and last source frames."""
        if not self.transition_bridges_enabled:
            log.info("FAL transition bridges disabled")
            return None

        try:
            import fal_client  # type: ignore
        except ImportError:
            log.warning("fal-client not installed")
            return None

        self._setup_env()
        model = os.getenv("FAL_TRANSITION_MODEL", _FLFV_MODEL)
        duration = str(int(round(duration_sec or self.transition_duration_sec)))
        arguments = _first_last_frame_arguments(
            model=model,
            start_image_url=_image_data_url(start_image_path),
            end_image_url=_image_data_url(end_image_path),
            prompt=_limit_prompt(prompt),
            duration=duration,
        )

        try:
            result = await fal_client.run_async(model, arguments=arguments)
        except Exception as e:
            result = await _retry_without_negative_prompt(
                fal_client=fal_client,
                model=model,
                arguments=arguments,
                error=e,
                label="FAL first/last-frame transition",
            )
            if result is None:
                return None

        return await self._download(result, out_path)

    async def text_to_video(
        self,
        prompt: str,
        out_path: Path,
        duration_sec: float = 5.0,
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
            arguments = _with_negative_prompt({
                "prompt": prompt,
                "duration": _scene_duration_value(duration_sec),
                "aspect_ratio": ratio,
            })
            result = await fal_client.run_async(
                _T2V_MODEL,
                arguments=arguments,
            )
        except Exception as e:
            result = await _retry_without_negative_prompt(
                fal_client=fal_client,
                model=_T2V_MODEL,
                arguments=arguments if "arguments" in locals() else {},
                error=e,
                label="FAL t2v",
            )
            if result is None:
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
    keep_tail = " Continuous visible camera motion from frame 0. High fidelity to source image. Calm commercial real-estate film."
    available = _MAX_PROMPT_CHARS - len(keep_tail) - 1
    return f"{cleaned[:available].rstrip()} {keep_tail}".strip()


def _with_negative_prompt(arguments: dict[str, str]) -> dict[str, str]:
    value = os.getenv("FAL_NEGATIVE_PROMPT", _NEGATIVE_PROMPT).strip()
    enabled = os.getenv("FAL_NEGATIVE_PROMPT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
    if enabled and value:
        return {**arguments, "negative_prompt": value}
    return arguments


async def _retry_without_negative_prompt(fal_client, model: str, arguments: dict, error: Exception, label: str):
    if "negative_prompt" not in arguments:
        log.exception("%s failed: %s", label, error)
        return None
    log.warning("%s failed with negative_prompt, retrying without it: %s", label, error)
    try:
        clean_arguments = dict(arguments)
        clean_arguments.pop("negative_prompt", None)
        return await fal_client.run_async(model, arguments=clean_arguments)
    except Exception as retry_error:
        log.exception("%s failed: %s", label, retry_error)
        return None


def _image_data_url(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        ext = image_path.suffix.lstrip(".").lower() or "jpeg"
        if ext == "jpg":
            ext = "jpeg"
        return f"data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"


def _scene_duration_value(duration_sec: float) -> str:
    return "10" if duration_sec > 5.0 else "5"


def _first_last_frame_arguments(
    model: str,
    start_image_url: str,
    end_image_url: str,
    prompt: str,
    duration: str,
) -> dict[str, str]:
    arguments = {
        "prompt": prompt,
        "duration": duration,
    }
    if "veo3.1/first-last-frame-to-video" in model:
        arguments.update({
            "first_frame_url": start_image_url,
            "last_frame_url": end_image_url,
        })
    elif "/o3/" in model:
        arguments.update({
            "image_url": start_image_url,
            "end_image_url": end_image_url,
        })
    else:
        arguments.update({
            "start_image_url": start_image_url,
            "end_image_url": end_image_url,
        })
    return _with_negative_prompt(arguments)
