"""
TTS Fallback Service.

Orchestrates Text-to-Speech synthesis across an ordered fallback chain:
1. Primary: ElevenLabs (eleven_multilingual_v2)
2. Fallback 1: Gemini TTS (gemini-2.5-flash)
3. Fallback 2: Local HF MMS-TTS (Meta MMS-TTS-TGL & MMS-TTS-IND)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.providers.fallback import (
    ProviderCandidate,
    ProviderResult,
    execute_with_fallback,
)
from app.core.providers.registry import ProviderRegistry
from app.integrations.gemini.tts import GeminiTTSProvider
from app.integrations.huggingface.tts import HFMMSTTSProvider
from app.integrations.piper.tts import PiperTTSProvider
from app.integrations.tts.client import TTSClient, ELEVENLABS_VOICE_PRESETS
from app.integrations.tts.models import TTSConfig, TTSSynthesisRecord

logger = get_logger(__name__)


class ElevenLabsTTSProvider:
    """Primary TTS Provider utilizing ElevenLabs."""

    def __init__(self):
        self.config = get_config()
        self.client = TTSClient(self.config.elevenlabs.api_key)
        self.is_configured = bool(self.config.elevenlabs.api_key and len(self.config.elevenlabs.api_key.strip()) > 5)

    async def synthesize(
        self,
        text: str,
        language: str = "fil-PH",
        voice: Optional[str] = None,
        market: str = "PH",
    ) -> TTSSynthesisRecord:
        if not self.is_configured:
            from app.core.providers.exceptions import ProviderConfigurationError
            raise ProviderConfigurationError("ElevenLabs API key not configured", provider="elevenlabs")

        default_voice = (
            ELEVENLABS_VOICE_PRESETS.get("PH_FILIPINO", {}).get("voice_id")
            if market == "PH"
            else ELEVENLABS_VOICE_PRESETS.get("ID_INDONESIAN", {}).get("voice_id")
        ) or "default_voice"
        cfg = TTSConfig(
            voice_id=voice or default_voice,
            language=language,
        )
        return self.client.synthesize_or_manifest(text, cfg, market)


class TTSService:
    """Provider-agnostic TTS caller with automatic fallback routing."""

    def __init__(self):
        self.eleven_provider = ElevenLabsTTSProvider()
        self.gemini_provider = GeminiTTSProvider()
        self.mms_provider = HFMMSTTSProvider()
        self.piper_provider = PiperTTSProvider()

    async def synthesize(
        self,
        text: str,
        language: str = "fil-PH",
        voice: Optional[str] = None,
        market: str = "PH",
        context: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Execute speech synthesis across ElevenLabs → Gemini TTS → HF MMS-TTS → Piper TTS.
        """
        candidates = [
            ProviderCandidate(
                name="elevenlabs",
                model="eleven_multilingual_v2",
                is_configured=self.eleven_provider.is_configured,
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self.eleven_provider.synthesize(text, language, voice, market),
            ),
            ProviderCandidate(
                name="gemini",
                model=get_config().gemini.tts_model,
                is_configured=self.gemini_provider.is_configured,
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self.gemini_provider.synthesize(text, language, voice, market),
            ),
            ProviderCandidate(
                name="hf_mms",
                model="facebook/mms-tts",
                is_configured=self.mms_provider.is_configured,
                verification_type="LOCAL VERIFIED",
                execute_fn=lambda: self.mms_provider.synthesize(text, language, voice, market),
            ),
            ProviderCandidate(
                name="piper",
                model="piper-neural-tts",
                is_configured=self.piper_provider.is_configured,
                verification_type="LOCAL VERIFIED",
                execute_fn=lambda: self.piper_provider.synthesize(text, language, voice, market),
            ),
        ]

        return await execute_with_fallback(
            providers=candidates,
            operation="speech_synthesis",
            context=context,
        )


_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
