"""Tests for localized fallback policies ensuring language and register continuity."""
import pytest
from app.localization.fallback import LocalizedFallbackManager
from app.localization.models import Language, Market, Register


class TestLocalizedFallback:
    def test_ph_taglish_fallback_does_not_switch_to_english(self):
        msg = LocalizedFallbackManager.get_fallback(
            market=Market.PH,
            language=Language.TAGLISH,
            reason="unsupported_kb",
            register=Register.FORMAL,
        )
        assert "Pasensya na po" in msg
        assert "verified na impormasyon" in msg
        assert "Bancassurance Specialist" in msg

    def test_id_formal_fallback_preserves_respectful_address(self):
        msg = LocalizedFallbackManager.get_fallback(
            market=Market.ID,
            language=Language.ID_FORMAL,
            reason="unsupported_kb",
            register=Register.FORMAL,
        )
        assert "Bapak/Ibu" in msg
        assert "layanan pembiayaan" in msg

    def test_id_colloquial_fallback_preserves_casual_warmth(self):
        msg = LocalizedFallbackManager.get_fallback(
            market=Market.ID,
            language=Language.ID_COLLOQUIAL,
            reason="unsupported_kb",
            register=Register.COLLOQUIAL,
        )
        assert "Kak" in msg
        assert "nih" in msg

    def test_human_escalation_fallback_preserves_language(self):
        ph_esc = LocalizedFallbackManager.get_fallback(
            market=Market.PH,
            language=Language.TAGLISH,
            reason="human_escalation",
        )
        assert "I-transfer ko na po kayo" in ph_esc

        id_esc = LocalizedFallbackManager.get_fallback(
            market=Market.ID,
            language=Language.ID_COLLOQUIAL,
            reason="human_escalation",
        )
        assert "langsung aku sambungkan" in id_esc
