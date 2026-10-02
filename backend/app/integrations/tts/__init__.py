"""TTS package exports."""
from app.integrations.tts.client import ELEVENLABS_VOICE_PRESETS, TTSClient
from app.integrations.tts.models import TTSConfig, TTSSynthesisRecord

__all__ = [
    "TTSConfig",
    "TTSSynthesisRecord",
    "TTSClient",
    "ELEVENLABS_VOICE_PRESETS",
]
