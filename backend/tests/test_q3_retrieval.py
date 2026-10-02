"""Tests for Q2 localized knowledge retrieval with market/language filters."""
import pytest
from app.agents.tools import search_knowledge


class TestQ3LocalizedRetrieval:
    def test_ph_grace_period_grounded_retrieval(self):
        res = search_knowledge(
            "Ano ang grace period bago mag-lapse ang policy?",
            filters={"market": "PH"},
        )
        assert res["grounded"] is True
        assert res["confidence"] >= 0.60
        assert "31-day grace period" in res["answer"]
        assert len(res["citations"]) > 0
        assert res["citations"][0]["source_name"] == "synthetic_ph_bancassurance.txt"

    def test_id_denda_and_jatuh_tempo_grounded_retrieval(self):
        res = search_knowledge(
            "Berapa denda keterlambatan jika melewati jatuh tempo?",
            filters={"market": "ID"},
        )
        assert res["grounded"] is True
        assert res["confidence"] >= 0.60
        assert "0.5%" in res["answer"]
        assert len(res["citations"]) > 0
        assert res["citations"][0]["source_name"] == "synthetic_id_multifinance.txt"

    def test_ph_unsupported_question_safe_abstention(self):
        res = search_knowledge(
            "Can I invest my bancassurance policy into cryptocurrency and offshore hedge funds?",
            filters={"market": "PH"},
        )
        assert res["grounded"] is False
        assert res["fallback_offered"] is True
        assert "don't have verified information" in res["answer"].lower()

    def test_id_unsupported_question_safe_abstention(self):
        res = search_knowledge(
            "Bisa nggak fasilitas pembiayaan ini dipakai buat trading forex tanpa jaminan?",
            filters={"market": "ID"},
        )
        assert res["grounded"] is False
        assert res["fallback_offered"] is True
        assert "don't have verified information" in res["answer"].lower()
