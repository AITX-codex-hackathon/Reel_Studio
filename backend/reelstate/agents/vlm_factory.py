"""Return the configured VLM client."""
from __future__ import annotations


def get_vlm_client():
    """Return the OpenAI vision/reasoning client used by editor agents."""
    from .openai_client import OpenAIClient

    return OpenAIClient()
