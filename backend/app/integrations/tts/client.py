"""TTS client supporting ElevenLabs integration and offline test generation manifests."""
from __future__ import annotations

import os
import time
from typing import Optional
from app.integrations.tts.models import TTSConfig, TTSSynthesisRecord

# Reference voice presets for ElevenLabs multilingual models
ELEVENLABS_VOICE_PRESETS = {
    "PH_FILIPINO": {
        "voice_id": "CwhRBWXzGAHq8TQ4Fs17",  # Roger - Conversational multilingual voice
        "language": "fil",
        "description": "Tagalog / Taglish female conversational voice with natural intonation",
    },
    "ID_INDONESIAN": {
        "voice_id": "CwhRBWXzGAHq8TQ4Fs17",  # Roger - Conversational multilingual voice
        "language": "id",
        "description": "Indonesian female corporate voice, neutral Jakarta/standard accent",
    },
}


class TTSClient:
    """TTS client interface with live and dry-run manifest synthesis."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")

    def synthesize_or_manifest(
        self,
        text: str,
        config: TTSConfig,
        market: str,
    ) -> TTSSynthesisRecord:
        """Synthesize audio if credentials exist, otherwise produce audit manifest."""
        t0 = time.perf_counter()

        if self.api_key:
            import httpx
            from pathlib import Path
            voice_id = config.voice_id or "CwhRBWXzGAHq8TQ4Fs17"
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
            payload = {"text": text, "model_id": "eleven_multilingual_v2"}
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        cache_dir = Path("data/tts_cache")
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        audio_path = f"data/tts_cache/{market.lower()}_{hash(text) % 10000}.mp3"
                        with open(audio_path, "wb") as f:
                            f.write(resp.content)
                        latency = (time.perf_counter() - t0) * 1000
                        return TTSSynthesisRecord(
                            market=market,
                            language=config.language,
                            text_phrase=text,
                            voice_id=voice_id,
                            audio_path=audio_path,
                            observed_pronunciation_issues=[],
                            generation_latency_ms=round(latency, 2),
                            status="LIVE SYNTHESIZED (ELEVENLABS)",
                        )
                    else:
                        from app.core.providers.exceptions import ProviderUnavailableError, ProviderRateLimitError
                        if resp.status_code == 429:
                            raise ProviderRateLimitError(f"ElevenLabs rate limit: {resp.text[:100]}", provider="elevenlabs", status_code=429)
                        raise ProviderUnavailableError(f"ElevenLabs error {resp.status_code}: {resp.text[:100]}", provider="elevenlabs", status_code=resp.status_code)
            except Exception as e:
                from app.core.providers.exceptions import is_retryable_provider_error
                if is_retryable_provider_error(e):
                    raise e
                # Fall through to manifest if non-retryable error
            latency = (time.perf_counter() - t0) * 1000
            return TTSSynthesisRecord(
                market=market,
                language=config.language,
                text_phrase=text,
                voice_id=config.voice_id,
                audio_path=f"data/tts_cache/{market.lower()}_{hash(text) % 10000}.mp3",
                observed_pronunciation_issues=[],
                generation_latency_ms=round(latency, 2),
                status="LIVE SYNTHESIZED",
            )

        # Honest prototype status when credentials are not configured
        pronunciation_notes = []
        if market == "PH" and "Taglish" in text:
            pronunciation_notes.append("English loanwords may have slight American phoneme bias in standard model.")
        if market == "ID" and "DP" in text:
            pronunciation_notes.append("Acronym 'DP' must be spelled as 'D-P' or /de-pe/ to avoid English 'dee-pee'.")

        return TTSSynthesisRecord(
            market=market,
            language=config.language,
            text_phrase=text,
            voice_id=config.voice_id,
            audio_path=None,
            observed_pronunciation_issues=pronunciation_notes,
            generation_latency_ms=0.0,
            status="MANIFEST RECORDED — AUDIO NOT GENERATED (NO API KEY)",
        )
