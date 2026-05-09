"""Return the configured VLM client (OpenAI or Claude)."""
from __future__ import annotations

import os


def get_vlm_client():
    """Return an OpenAIClient or ClaudeClient based on VLM_PROVIDER env var."""
    provider = os.getenv("VLM_PROVIDER", "claude").lower()
    if provider == "openai":
        from .openai_client import OpenAIClient
        return OpenAIClient()
    from .claude_client import ClaudeClient
    return ClaudeClient()
