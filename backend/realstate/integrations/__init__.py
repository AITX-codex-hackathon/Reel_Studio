"""External API adapters. Each gracefully degrades to None when keys are missing."""
from .fal_image import FalImageClient
from .nano_banana import NanoBananaClient
from .runway import RunwayClient
from .elevenlabs import ElevenLabsClient
from .stock_audio import StockAudioLibrary

__all__ = [
    "FalImageClient",
    "NanoBananaClient",
    "RunwayClient",
    "ElevenLabsClient",
    "StockAudioLibrary",
]
