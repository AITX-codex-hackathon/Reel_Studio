"""OpenAI VLM client — same interface as ClaudeClient."""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

from .claude_client import ClaudeUnavailable  # shared unavailability sentinel

log = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        vision_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("VLM_MODEL", "gpt-4o")
        self.vision_model = vision_model or self.model
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client_or_raise(self):
        if not self.enabled:
            raise ClaudeUnavailable("OPENAI_API_KEY is not set")
        if self._client is None:
            try:
                from openai import AsyncOpenAI  # type: ignore
            except ImportError as e:
                raise ClaudeUnavailable("openai SDK not installed: pip install openai") from e
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def message(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        client = self._client_or_raise()
        resp = await client.chat.completions.create(
            model=model or self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def vision(
        self,
        system: str,
        user_text: str,
        image_path: Path,
        max_tokens: int = 1024,
    ) -> str:
        client = self._client_or_raise()

        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime:
            mime = "image/jpeg"

        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode()

        resp = await client.chat.completions.create(
            model=self.vision_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}", "detail": "high"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
            ],
        )
        return resp.choices[0].message.content or ""
