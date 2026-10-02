"""Tests for market-specific domain terminology dictionaries and normalization."""
import pytest
from app.localization.models import Market
from app.localization.terminology import ID_TERMINOLOGY, PH_TERMINOLOGY


class TestTerminology:
    def test_ph_terminology_lookup_and_concepts(self):
        # Look up by term
        item = PH_TERMINOLOGY.get_by_term("premium")
        assert item is not None
        assert item.canonical_concept == "premium"

        # Look up by variant
        var_item = PH_TERMINOLOGY.get_by_term("hulog")
        assert var_item is not None
        assert var_item.canonical_concept == "premium"

        rider_item = PH_TERMINOLOGY.get_by_concept("rider")
        assert rider_item is not None
        assert "add-on" in rider_item.allowed_variants

    def test_id_terminology_lookup_and_concepts(self):
        # Test required terms: cicilan, tenor, denda, DP, jatuh tempo, angsuran, pembiayaan
        for term, expected_concept in [
            ("cicilan", "installment"),
            ("tenor", "tenor"),
            ("denda", "late_penalty"),
            ("dp", "down_payment"),
            ("jatuh tempo", "due_date"),
            ("angsuran", "installment_formal"),
            ("pembiayaan", "financing"),
        ]:
            item = ID_TERMINOLOGY.get_by_term(term)
            assert item is not None, f"Failed to find {term}"
            assert item.canonical_concept == expected_concept

    def test_find_terms_in_utterance(self):
        text_id = "Berapa cicilan per bulan kalau DP saya 20 juta dan tenor 36 bulan sebelum jatuh tempo?"
        found = ID_TERMINOLOGY.find_terms_in_text(text_id)
        concepts = {f.canonical_concept for f in found}
        assert "installment" in concepts
        assert "down_payment" in concepts
        assert "tenor" in concepts
        assert "due_date" in concepts

        text_ph = "Gusto ko po malaman kung magkano ang monthly premium kapag may critical illness rider sa policy."
        found_ph = PH_TERMINOLOGY.find_terms_in_text(text_ph)
        concepts_ph = {f.canonical_concept for f in found_ph}
        assert "premium" in concepts_ph
        assert "rider" in concepts_ph
        assert "policy" in concepts_ph

    def test_normalize_slang_variants(self):
        text = "Gimana kalau uang muka dan angsuran bulanan disesuaikan?"
        norm = ID_TERMINOLOGY.normalize_text(text)
        # 'uang muka' normalized to DP
        assert "DP" in norm
