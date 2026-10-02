"""Tests for heuristic language, dialect, and register detection."""
import pytest
from app.localization.language import LanguageDetector, detect_language
from app.localization.models import Language, Market, Register


class TestLanguageDetection:
    def test_ph_english_detection(self):
        text = "Hello, I would like to inquire about business loan interest rates."
        res = detect_language(text, market_hint=Market.PH)
        assert res.detected_language == Language.EN
        assert res.code_switch_detected is False

    def test_ph_pure_tagalog_detection(self):
        text = "Magandang araw po sa inyo, nais ko po sanang magtanong ukol sa proteksyon."
        res = detect_language(text, market_hint=Market.PH)
        assert res.detected_language == Language.FIL
        assert res.register == Register.FORMAL

    def test_ph_taglish_code_switching(self):
        text = "Hello po, magkano po ang monthly premium kung mag-a-apply ako ng life insurance policy plan?"
        res = detect_language(text, market_hint=Market.PH)
        assert res.detected_language == Language.TAGLISH
        assert res.code_switch_detected is True
        assert res.register == Register.FORMAL

    def test_id_formal_detection(self):
        text = "Selamat pagi Bapak/Ibu, saya ingin mengajukan fasilitas pembiayaan multiguna untuk modal usaha."
        res = detect_language(text, market_hint=Market.ID)
        assert res.detected_language == Language.ID_FORMAL
        assert res.register == Register.FORMAL

    def test_id_colloquial_detection(self):
        text = "Halo Kak! Mau nanya dong, ada promo DP ringan nggak buat kredit motor?"
        res = detect_language(text, market_hint=Market.ID)
        assert res.detected_language == Language.ID_COLLOQUIAL
        assert res.register == Register.COLLOQUIAL
        assert res.code_switch_detected is True  # 'DP'

    def test_empty_string_handling(self):
        res = detect_language("", market_hint=Market.PH)
        assert res.confidence == 0.5
        assert res.is_development_fallback is True
