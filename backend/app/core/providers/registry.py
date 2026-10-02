"""
Provider Registry and Modality Dispatcher.

Manages provider chains for:
- LLM: OpenAI (primary) → Gemini → Groq → OpenRouter
- ASR: Deepgram (primary) → Gemini Transcribe → HF Whisper
- TTS: ElevenLabs (primary) → Gemini TTS → HF MMS
- Voice: Vapi (primary) → Gemini Live

Also generates provider status summaries for GET /api/v1/providers/status.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from app.core.config import get_config
from app.core.providers.health import get_health_tracker


class ProviderRegistry:
    """Registry managing provider chains, configuration states, and health."""

    @staticmethod
    def is_provider_configured(name: str) -> bool:
        config = get_config()
        p = name.lower()
        if p == "openai":
            return bool(config.openai.api_key and len(config.openai.api_key) > 5)
        elif p in ("gemini", "gemini_transcribe", "gemini_tts", "gemini_live"):
            return bool(config.gemini.api_key and len(config.gemini.api_key) > 5)
        elif p == "groq":
            return bool(config.groq.api_key and len(config.groq.api_key) > 5)
        elif p == "openrouter":
            return bool(config.openrouter.api_key and len(config.openrouter.api_key) > 5)
        elif p == "deepgram":
            return bool(config.deepgram.api_key and len(config.deepgram.api_key) > 5)
        elif p == "elevenlabs":
            return bool(config.elevenlabs.api_key and len(config.elevenlabs.api_key) > 5)
        elif p == "vapi":
            return bool(config.vapi.public_key and config.vapi.assistant_id)
        elif p in ("hf_whisper", "hf_mms", "hf_local", "piper"):
            return True
        return False

    @staticmethod
    def get_status_overview() -> Dict[str, Dict[str, str]]:
        """Return provider configuration matrix without exposing keys."""
        config = get_config()
        return {
            "llm": {
                "openai": "configured" if bool(config.openai.api_key) else "not_configured",
                "gemini": "configured" if bool(config.gemini.api_key) else "not_configured",
                "groq": "configured" if bool(config.groq.api_key) else "not_configured",
                "openrouter": "configured" if bool(config.openrouter.api_key) else "not_configured",
            },
            "asr": {
                "deepgram": "configured" if bool(config.deepgram.api_key) else "not_configured",
                "gemini": "configured" if bool(config.gemini.api_key) else "not_configured",
                "hf_whisper": "available" if config.hf.local_enabled else "disabled",
            },
            "tts": {
                "elevenlabs": "configured" if bool(config.elevenlabs.api_key) else "not_configured",
                "gemini": "configured" if bool(config.gemini.api_key) else "not_configured",
                "hf_mms": "available" if config.hf.local_enabled else "disabled",
                "piper": "available",
            },
            "voice": {
                "vapi": "configured" if bool(config.vapi.public_key and config.vapi.assistant_id) else "not_configured",
                "gemini_live": "configured" if bool(config.gemini.api_key) else "not_configured",
            },
        }

    @staticmethod
    def get_llm_chain() -> List[str]:
        return ["openai", "gemini", "groq", "openrouter"]

    @staticmethod
    def get_asr_chain() -> List[str]:
        return ["deepgram", "gemini", "hf_whisper"]

    @staticmethod
    def get_tts_chain() -> List[str]:
        return ["elevenlabs", "gemini", "hf_mms", "piper"]

    @staticmethod
    def get_voice_chain() -> List[str]:
        return ["vapi", "gemini_live"]
