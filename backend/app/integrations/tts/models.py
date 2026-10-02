"""Text-to-Speech (TTS) configuration models and latency tracking schemas."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TTSConfig(BaseModel):
    """Configuration for Text-to-Speech synthesis."""
    provider: str = "elevenlabs"
    model: str = "eleven_multilingual_v2"
    voice_id: str
    language: str
    latency_target: int = 250  # milliseconds
    stability: float = 0.50
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


class TTSSynthesisRecord(BaseModel):
    """Record of a TTS generation test or runtime synthesis."""
    market: str
    language: str
    text_phrase: str
    voice_id: str
    audio_path: Optional[str] = None
    observed_pronunciation_issues: list[str] = Field(default_factory=list)
    generation_latency_ms: float = 0.0
    status: str = "TEST CASE PREPARED — AUDIO NOT YET AVAILABLE"
