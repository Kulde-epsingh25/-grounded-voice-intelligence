"""
Hugging Face open-model integration layer for Q2 retrieval, Q3 ASR/TTS, and Q4 evaluation.
"""

from app.integrations.hf.client import HFInferenceClient, HF_SUPPORTED_MODELS
from app.integrations.hf.models import (
    HFASRComparisonResult,
    HFModelSpec,
    HFRetrievalBenchmarkResult,
    HFTTSComparisonResult,
)

__all__ = [
    "HFInferenceClient",
    "HF_SUPPORTED_MODELS",
    "HFModelSpec",
    "HFRetrievalBenchmarkResult",
    "HFASRComparisonResult",
    "HFTTSComparisonResult",
]
