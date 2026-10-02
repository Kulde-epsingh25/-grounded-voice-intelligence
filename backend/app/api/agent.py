"""Stateful HTTP interface for the browser-based Q1 voice-agent demo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.agents.base import VoiceAgent

router = APIRouter()
_agent_sessions: dict[str, VoiceAgent] = {}


class AgentTurnRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    call_id: str = Field(min_length=1, max_length=128)
    # Kept for compatibility with the current browser client. Server session
    # state remains authoritative so callers cannot overwrite qualification data.
    state: dict[str, Any] = Field(default_factory=dict)


@router.post("/turn")
async def process_agent_turn(request: AgentTurnRequest) -> dict[str, Any]:
    """Process one browser turn with the same Q1 agent used by provider sessions."""
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Transcript must not be empty")

    agent = _agent_sessions.get(request.call_id)
    if agent is None:
        agent = VoiceAgent(call_id=request.call_id)
        _agent_sessions[request.call_id] = agent

    turn = agent.process_turn(transcript)
    return {
        "call_id": request.call_id,
        "turn_index": turn.turn_index,
        "response": turn.assistant_response,
        "state": agent.public_state(),
        "grounded": turn.grounded,
        "citations": turn.citations_used,
        "escalated": agent.escalated,
    }


@router.delete("/sessions/{call_id}", status_code=204)
async def end_agent_session(call_id: str) -> Response:
    """Release the in-memory browser session when the caller ends the demo."""
    _agent_sessions.pop(call_id, None)
    return Response(status_code=204)