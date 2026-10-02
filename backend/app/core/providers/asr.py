"""
ASR Fallback Service.

Orchestrates Speech-to-Text across an ordered fallback chain:
1. Primary: Deepgram (Nova-3)
2. Fallback 1: Gemini Transcribe (Gemini 2.5 Flash Multimodal Audio)
3. Fallback 2: Local HF Whisper (Whisper Large V3 Turbo)
"""

from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.providers.fallback import (
    ProviderCandidate,
    ProviderResult,
    execute_with_fallback,
)
from app.core.providers.registry import ProviderRegistry
from app.integrations.gemini.transcription import GeminiTranscriptionProvider, Transcript
from app.integrations.huggingface.whisper import HFWhisperProvider

logger = get_logger(__name__)


class DeepgramASRClient:
    """Primary ASR Provider utilizing Deepgram Nova 3."""

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.deepgram.api_key
        self.is_configured = bool(self.api_key and len(self.api_key.strip()) > 5)

    async def transcribe(
        self,
        audio: bytes,
        language: Optional[str] = None,
        diarization: bool = False,
    ) -> Transcript:
        if not self.is_configured:
            # When unconfigured in prototype mode, raise so fallback can trigger
            from app.core.providers.exceptions import ProviderConfigurationError
            raise ProviderConfigurationError("Deepgram API key not configured", provider="deepgram")

        url = "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true"
        if language and language != "auto":
            url += f"&language={language}"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, content=audio)
            resp.raise_for_status()
            data = resp.json()
            channels = data.get("results", {}).get("channels", [])
            transcript_text = ""
            conf = 0.95
            if channels:
                alts = channels[0].get("alternatives", [])
                if alts:
                    transcript_text = alts[0].get("transcript", "")
                    conf = alts[0].get("confidence", 0.95)

            return Transcript(
                text=transcript_text,
                language=language or "auto",
                confidence=conf,
                is_final=True,
                provider="deepgram",
                raw_response=data,
            )


class ASRService:
    """Provider-agnostic ASR caller with automatic fallback routing."""

    def __init__(self):
        self.deepgram_client = DeepgramASRClient()
        self.gemini_provider = GeminiTranscriptionProvider()
        self.whisper_provider = HFWhisperProvider()

    async def transcribe(
        self,
        audio: bytes,
        language: Optional[str] = None,
        diarization: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Execute speech transcription across Deepgram → Gemini → HF Whisper.
        """
        candidates = [
            ProviderCandidate(
                name="deepgram",
                model="nova-3",
                is_configured=self.deepgram_client.is_configured,
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self.deepgram_client.transcribe(audio, language, diarization),
            ),
            ProviderCandidate(
                name="gemini",
                model=get_config().gemini.transcribe_model,
                is_configured=self.gemini_provider.is_configured,
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self.gemini_provider.transcribe(audio, language, diarization),
            ),
            ProviderCandidate(
                name="hf_whisper",
                model="openai/whisper-large-v3-turbo",
                is_configured=self.whisper_provider.is_configured,
                verification_type="LOCAL VERIFIED",
                execute_fn=lambda: self.whisper_provider.transcribe(audio, language, diarization),
            ),
        ]

        return await execute_with_fallback(
            providers=candidates,
            operation="speech_transcription",
            context=context,
        )


_asr_service: Optional[ASRService] = None


def get_asr_service() -> ASRService:
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService()
    return _asr_service
