"""Tests for Philippines and Indonesia market configs and Vapi assistant generator."""
import pytest
from app.integrations.vapi.assistant import (
    build_indonesia_assistant,
    build_philippines_assistant,
)
from app.localization.market import get_market_config, list_supported_markets
from app.localization.models import Language, Market, Sector


class TestMarketConfigs:
    def test_ph_market_config(self):
        cfg = get_market_config(Market.PH)
        assert cfg.market == Market.PH
        assert cfg.sector == Sector.BANCASSURANCE
        assert Language.TAGLISH in cfg.supported_languages
        assert cfg.transcriber_config["model"] == "nova-3"
        assert cfg.transcriber_config["language"] == "multi"
        assert cfg.tts_config["language"] == "fil"
        assert "po" in cfg.politeness_particles

    def test_id_market_config(self):
        cfg = get_market_config(Market.ID)
        assert cfg.market == Market.ID
        assert cfg.sector == Sector.MULTIFINANCE
        assert Language.ID_COLLOQUIAL in cfg.supported_languages
        assert cfg.transcriber_config["model"] == "nova-3"
        assert cfg.transcriber_config["language"] == "multi"
        assert cfg.tts_config["language"] == "id"
        assert "Bapak" in cfg.politeness_particles

    def test_list_supported_markets(self):
        markets = list_supported_markets()
        assert Market.PH in markets
        assert Market.ID in markets

    def test_build_ph_assistant_config(self):
        asst = build_philippines_assistant("http://localhost:8000")
        assert asst.name == "Philippines Bancassurance Assistant"
        assert asst.transcriber["provider"] == "deepgram"
        assert asst.transcriber["language"] == "multi"
        assert len(asst.tools) >= 4

    def test_build_id_assistant_config(self):
        asst = build_indonesia_assistant("http://localhost:8000")
        assert asst.name == "Indonesia Multifinance Assistant"
        assert asst.voice["provider"] == "11labs"
        assert asst.transcriber["language"] == "multi"
        assert len(asst.tools) >= 4

    def test_invalid_market_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported market"):
            get_market_config("SG")
