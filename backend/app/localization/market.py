"""Market registry and configuration loader for Philippines and Indonesia."""
from __future__ import annotations

from typing import Optional
from app.localization.indonesia import ID_MARKET_CONFIG
from app.localization.models import Market, MarketConfig
from app.localization.philippines import PH_MARKET_CONFIG

MARKET_REGISTRY: dict[Market, MarketConfig] = {
    Market.PH: PH_MARKET_CONFIG,
    Market.ID: ID_MARKET_CONFIG,
}


def get_market_config(market: Market | str) -> MarketConfig:
    """Retrieve market configuration by Market enum or ISO country code."""
    market_str = market.value if isinstance(market, Market) else str(market).upper()
    try:
        market_enum = Market(market_str)
    except ValueError:
        raise ValueError(f"Unsupported market '{market}'. Available: {[m.value for m in Market]}")

    if market_enum not in MARKET_REGISTRY:
        raise ValueError(f"Unsupported market '{market}'. Available: {[m.value for m in Market]}")

    return MARKET_REGISTRY[market_enum]


def list_supported_markets() -> list[Market]:
    """List all supported markets."""
    return list(MARKET_REGISTRY.keys())
