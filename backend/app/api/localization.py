"""Interactive text/voice-demo API for the localized Q3 agents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.localization.agent import LocalizedVoiceAgent
from app.localization.market import get_market_config, list_supported_markets
from app.localization.models import Market

router = APIRouter()
_sessions: dict[str, tuple[Market, LocalizedVoiceAgent]] = {}


class LocalizedTurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    transcript: str = Field(min_length=1, max_length=4000)


@router.get("/markets")
async def get_markets() -> list[dict[str, Any]]:
    """Return supported market, sector, speech, and greeting configuration."""
    markets = []
    for market in list_supported_markets():
        config = get_market_config(market)
        phrasing = config.phrasings.get(config.default_language)
        markets.append(
            {
                "market": config.market.value,
                "sector": config.sector.value,
                "supported_languages": [language.value for language in config.supported_languages],
                "default_language": config.default_language.value,
                "default_register": config.default_register.value,
                "asr": config.transcriber_config,
                "tts": config.tts_config,
                "greeting": phrasing.greeting[0] if phrasing and phrasing.greeting else "",
            }
        )
    return markets


@router.post("/{market}/turn")
async def process_localized_turn(market: str, request: LocalizedTurnRequest) -> dict[str, Any]:
    """Run one utterance through the stateful Philippines or Indonesia agent."""
    try:
        selected_market = Market(market.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Supported markets are PH and ID.") from exc

    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Transcript must not be empty.")

    existing = _sessions.get(request.session_id)
    if existing and existing[0] != selected_market:
        raise HTTPException(
            status_code=409,
            detail="This session is already assigned to a different market. Start a new session to switch markets.",
        )

    if existing:
        agent = existing[1]
    else:
        agent = LocalizedVoiceAgent(market=selected_market, call_id=request.session_id)
        _sessions[request.session_id] = (selected_market, agent)

    previous_term_count = len(agent.detected_terms)
    turn = agent.process_turn(transcript)
    detection = agent.last_detection
    return {
        "session_id": request.session_id,
        "turn_index": turn.turn_index,
        "market": selected_market.value,
        "sector": agent.market_config.sector.value,
        "response": turn.assistant_response,
        "grounded": turn.grounded,
        "citations": turn.citations_used,
        "language": agent.current_language.value,
        "register": agent.current_register.value,
        "language_confidence": detection.confidence if detection else 0.0,
        "code_switch_detected": agent.detected_code_switch,
        "detected_terms": [
            term.canonical_concept for term in agent.detected_terms[previous_term_count:]
        ],
        "state": turn.state_after.value,
        "escalated": agent.escalated,
        "lead_created": agent.lead_created,
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def end_localized_session(session_id: str) -> Response:
    """Release the server-side market demo session."""
    _sessions.pop(session_id, None)
    return Response(status_code=204)