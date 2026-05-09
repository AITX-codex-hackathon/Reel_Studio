"""Thin wrapper around Anthropic SDK with graceful degradation.

If ANTHROPIC_API_KEY is not set, calls raise ClaudeUnavailable, and the agent
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


class ClaudeUnavailable(RuntimeError):
    pass


class ClaudeClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        vision_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
        self.vision_model = vision_model or os.getenv("CLAUDE_VISION_MODEL", "claude-sonnet-4-6")
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client_or_raise(self):
        if not self.enabled:
            raise ClaudeUnavailable("ANTHROPIC_API_KEY is not set")
        if self._client is None:
            try:
                import anthropic  # type: ignore
            except ImportError as e:
                raise ClaudeUnavailable("anthropic SDK not installed: pip install anthropic") from e
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def message(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        client = self._client_or_raise()
        resp = await client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    async def vision(
        self,
        system: str,
        user_text: str,
        image_path: Path,
        max_tokens: int = 1024,
    ) -> str:
        """Send a single image + text prompt to Claude and return text."""
        client = self._client_or_raise()

        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime:
            mime = "image/jpeg"

        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode()

        resp = await client.messages.create(
            model=self.vision_model,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": mime, "data": data},
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
