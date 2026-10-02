"""
Unit tests for Hugging Face open-model integration layer and comparative benchmark runner.
"""

from __future__ import annotations

import pytest
from app.integrations.hf.client import HFInferenceClient, HF_SUPPORTED_MODELS
from app.integrations.hf.models import (
    HFASRComparisonResult,
    HFModelSpec,
    HFRetrievalBenchmarkResult,
    HFTTSComparisonResult,
)


class TestHFIntegration:
    """Test suite for Hugging Face client, model specifications, and evaluation metrics."""

    def test_hf_supported_models_catalog(self):
        """Ensure all required HF open-models are registered with complete specs."""
        required_models = [
            "BAAI/bge-m3",
            "BAAI/bge-reranker-v2-m3",
            "openai/whisper-large-v3-turbo",
            "openai/whisper-large-v3",
            "facebook/mms-tts-tgl",
            "facebook/mms-tts-ind",
            "ai4bharat/indic-conformer-600m-multilingual",
            "ai4bharat/IndicF5",
        ]
        for model_id in required_models:
            assert model_id in HF_SUPPORTED_MODELS
            spec = HF_SUPPORTED_MODELS[model_id]
            assert isinstance(spec, HFModelSpec)
            assert spec.model_id == model_id
            assert len(spec.languages) > 0
            assert len(spec.pros) > 0

    def test_hf_client_initialization_offline(self):
        """Test client defaults gracefully to benchmark mode when no token is present."""
        client = HFInferenceClient(api_token="")
        assert client.is_live is False
        assert "OFFLINE AUDIT" in client.status_label

    def test_hf_client_initialization_with_token(self):
        """Test client recognizes live mode when token is provided."""
        client = HFInferenceClient(api_token="hf_test_token_123456789")
        assert client.is_live is True
        assert "LIVE HF INFERENCE PROVIDER" in client.status_label

    def test_bge_m3_similarity_scoring(self):
        """Test deterministic BGE-M3 similarity score calculation."""
        import asyncio
        client = HFInferenceClient()
        query = "What is the interest rate and maximum loan amount for Starter loans?"
        docs = [
            "Starter business loans offer up to 2000000 with 12.5% interest rate.",
            "Weather forecast for Tokyo tomorrow is sunny.",
        ]
        scores = asyncio.run(client.compute_similarity_bge(query, docs))
        assert len(scores) == 2
        assert scores[0] > scores[1]  # Financial doc should have higher relevance than Tokyo weather

    def test_wer_calculation_identical(self):
        """Test Word Error Rate on identical strings."""
        from scripts.eval_hf_models import calculate_wer
        assert calculate_wer("test sentence", "test sentence") == 0.0

    def test_wer_calculation_substitutions(self):
        """Test Word Error Rate with known substitutions."""
        from scripts.eval_hf_models import calculate_wer
        wer = calculate_wer("grace period before policy lapse", "grace period before policy lapsing")
        assert 0.0 < wer < 0.5
