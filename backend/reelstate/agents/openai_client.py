"""Thin wrapper around the OpenAI SDK with graceful degradation.

If OPENAI_API_KEY is not set, calls raise OpenAIUnavailable, and the agent
layer is expected to fall back to deterministic logic (heuristic shot matching,
no prompt translation).
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


class OpenAIUnavailable(RuntimeError):
    pass


class OpenAIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        vision_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_AGENT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.vision_model = (
            vision_model
            or os.getenv("OPENAI_ANALYZER_MODEL")
            or os.getenv("VLM_MODEL")
            or os.getenv("OPENAI_AGENT_MODEL")
            or os.getenv("OPENAI_VISION_MODEL", "gpt-5.5")
        )
        self.fallback_models = _split_models(
            os.getenv("OPENAI_MODEL_FALLBACKS", "gpt-5.2,gpt-5,gpt-4o")
        )
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client_or_raise(self):
        if not self.enabled:
            raise OpenAIUnavailable("OPENAI_API_KEY is not set")
        if self._client is None:
            try:
                from openai import AsyncOpenAI  # type: ignore
            except ImportError as e:
                raise OpenAIUnavailable("openai SDK not installed: pip install openai") from e
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def message(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        response_format: Optional[dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> str:
        client = self._client_or_raise()
        last_error: Optional[Exception] = None
        for candidate in self._model_candidates(model or self.model):
            kwargs: dict[str, Any] = {
                "model": candidate,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if response_format:
                kwargs["response_format"] = response_format
            if temperature is not None and _supports_custom_temperature(candidate):
                kwargs["temperature"] = temperature
            try:
                resp = await _create_chat_completion(client, kwargs)
                return resp.choices[0].message.content or ""
            except Exception as error:
                last_error = error
                if not _looks_like_model_error(error):
                    raise
                log.warning("OpenAI model %s failed, trying fallback if available: %s", candidate, error)
        if last_error:
            raise last_error
        raise OpenAIUnavailable("No OpenAI model candidates configured")

    async def vision(
        self,
        system: str,
        user_text: str,
        image_path: Path,
        max_tokens: int = 1024,
        response_format: Optional[dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Send a single image + text prompt to the vision model and return text."""
        client = self._client_or_raise()

        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime:
            mime = "image/jpeg"

        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode()

        last_error: Optional[Exception] = None
        for candidate in self._model_candidates(self.vision_model):
            kwargs: dict[str, Any] = {
                "model": candidate,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{data}"},
                            },
                        ],
                    },
                ],
            }
            if response_format:
                kwargs["response_format"] = response_format
            if temperature is not None and _supports_custom_temperature(candidate):
                kwargs["temperature"] = temperature
            try:
                resp = await _create_chat_completion(client, kwargs)
                return resp.choices[0].message.content or ""
            except Exception as error:
                last_error = error
                if not _looks_like_model_error(error):
                    raise
                log.warning("OpenAI vision model %s failed, trying fallback if available: %s", candidate, error)
        if last_error:
            raise last_error
        raise OpenAIUnavailable("No OpenAI vision model candidates configured")

    def _model_candidates(self, primary: Optional[str]) -> list[str]:
        candidates: list[str] = []
        for model in [primary, *self.fallback_models]:
            if model and model not in candidates:
                candidates.append(model)
        return candidates


async def _create_chat_completion(client, kwargs: dict[str, Any]):
    """Call Chat Completions with small compatibility retries for newer models."""
    try:
        return await client.chat.completions.create(**kwargs)
    except Exception as error:
        message = str(error).lower()
        if "max_tokens" in kwargs and "max_completion_tokens" in message:
            retry = dict(kwargs)
            retry["max_completion_tokens"] = retry.pop("max_tokens")
            return await client.chat.completions.create(**retry)
        if "temperature" in kwargs and "temperature" in message and (
            "unsupported" in message or "does not support" in message or "invalid" in message
        ):
            retry = dict(kwargs)
            retry.pop("temperature", None)
            return await client.chat.completions.create(**retry)
        raise


def _split_models(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _looks_like_model_error(error: Exception) -> bool:
    message = str(error).lower()
    if "model" not in message:
        return False
    return any(
        term in message
        for term in (
            "does not exist",
            "not found",
            "unsupported",
            "not supported",
            "invalid",
            "access",
            "permission",
        )
    )


def _supports_custom_temperature(model: str) -> bool:
    return not model.lower().startswith("gpt-5")
