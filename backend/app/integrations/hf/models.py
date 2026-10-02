"""
Data models and configuration specifications for Hugging Face open-model comparisons.
"""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class HFModelSpec(BaseModel):
    """Specification of a Hugging Face hosted or local open model."""
    model_id: str
    task: str
    family: str
    parameters: str
    languages: List[str]
    streaming_capable: bool = False
    self_hosted_possible: bool = True
    inference_provider_available: bool = True
    intended_role: str
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)


class HFRetrievalBenchmarkResult(BaseModel):
    """Comparison result for a single retrieval query between baseline and HF models."""
    query_id: str
    query_text: str
    query_language: str
    baseline_source: Optional[str]
    baseline_confidence: float
    baseline_grounded: bool
    bge_m3_score: float
    bge_reranker_score: float
    bge_m3_grounded: bool
    verdict: str


class HFASRComparisonResult(BaseModel):
    """Comparative speech-to-text benchmark between streaming vendor and HF reference."""
    audio_id: str
    market: str
    language: str
    reference_transcript: str
    deepgram_streaming_transcript: str
    whisper_turbo_transcript: str
    deepgram_wer: float
    whisper_wer: float
    deepgram_latency_ms: float
    whisper_latency_ms: float
    critical_terms_preserved_deepgram: bool
    critical_terms_preserved_whisper: bool


class HFTTSComparisonResult(BaseModel):
    """Comparative text-to-speech assessment between cloud vendor and Meta MMS."""
    market: str
    language: str
    sample_text: str
    elevenlabs_voice_id: str
    elevenlabs_latency_ms: float
    mms_model_id: str
    mms_parameters: str
    mms_latency_ms: float
    data_residency_compliant_local: bool
    expressive_reassurance_quality: str
