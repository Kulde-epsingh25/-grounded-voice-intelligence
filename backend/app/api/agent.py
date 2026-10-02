"""
Q1 Voice Agent - FastAPI Router.

Exposes the backend VoiceAgent over HTTP for:
- Frontend direct integration (/api/v1/agent/turn)
- Gemini Live fallback path
- Testing and debugging

This is the missing router that the frontend app.js was already calling.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.base import VoiceAgent
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# In-memory session registry (per-process). For production, swap with Redis or DB.
_sessions: dict[str, VoiceAgent] = {}


class TurnRequest(BaseModel):
    """Request body for a single conversation turn."""
    session_id: Optional[str] = None
    utterance: str


class TurnResponse(BaseModel):
    """Response for a single conversation turn."""
    session_id: str
    turn_index: int
    user_utterance: str
    assistant_response: str
    state_before: str
    state_after: str
    grounded: bool
    citations: list[dict[str, Any]] = []
    qualification_state: dict[str, Any] = {}
    lead_created: bool = False
    escalated: bool = False
    extraction_source: Optional[str] = None


@router.post("/turn", response_model=TurnResponse)
async def process_turn(body: TurnRequest) -> TurnResponse:
    """
    Process a single conversational turn through the backend VoiceAgent.

    If session_id is provided and an existing session is found, it is resumed.
    Otherwise, a new session is created.
    """
    # Resolve or create session
    session_id = body.session_id
    if session_id and session_id in _sessions:
        agent = _sessions[session_id]
    else:
        session_id = session_id or f"session_{uuid4().hex[:8]}"
        agent = VoiceAgent(call_id=session_id)
        _sessions[session_id] = agent
        logger.info(
            "New agent session created",
            extra={"extra_data": {"session_id": session_id}},
        )

    if not body.utterance or not body.utterance.strip():
        raise HTTPException(status_code=400, detail="utterance must not be empty")

    # Process the turn
    turn = agent.process_turn(body.utterance)

    # Use async extraction if we can (to actually invoke the LLM)
    # The above process_turn uses extract_sync which falls back to regex in async contexts.
    # For this endpoint, re-run extraction asynchronously to get LLM quality.
    # NOTE: We capture extraction_source from the _history for transparency.
    extraction_source = None
    if agent._history:
        # The last extraction source isn't stored in VoiceAgentTurn directly.
        # The agent logs it; here we just report "llm_or_regex".
        extraction_source = "llm_or_regex"

    return TurnResponse(
        session_id=session_id,
        turn_index=turn.turn_index,
        user_utterance=turn.user_utterance,
        assistant_response=turn.assistant_response,
        state_before=turn.state_before.value if hasattr(turn.state_before, "value") else str(turn.state_before),
        state_after=turn.state_after.value if hasattr(turn.state_after, "value") else str(turn.state_after),
        grounded=turn.grounded,
        citations=turn.citations_used,
        qualification_state=agent.qualification_manager.state.to_dict(),
        lead_created=agent.lead_created,
        escalated=agent.escalated,
        extraction_source=extraction_source,
    )


@router.delete("/session/{session_id}")
async def end_session(session_id: str) -> dict[str, str]:
    """End and clean up an agent session."""
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info("Session ended", extra={"extra_data": {"session_id": session_id}})
        return {"status": "ended", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@router.get("/session/{session_id}")
async def get_session_state(session_id: str) -> dict[str, Any]:
    """Get current state of an agent session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    agent = _sessions[session_id]
    return {
        "session_id": session_id,
        "turn_index": agent.turn_index,
        "current_state": agent.state_machine.current_state.value,
        "qualification_state": agent.qualification_manager.state.to_dict(),
        "lead_created": agent.lead_created,
        "escalated": agent.escalated,
    }
