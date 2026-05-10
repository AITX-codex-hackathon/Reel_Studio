"""External API adapters. Each gracefully degrades to None when keys are missing."""
from .nano_banana import NanoBananaClient
from .runway import RunwayClient
from .elevenlabs import ElevenLabsClient
from .stock_audio import StockAudioLibrary

__all__ = [
    "NanoBananaClient",
    "RunwayClient",
    "ElevenLabsClient",
    "StockAudioLibrary",
]
