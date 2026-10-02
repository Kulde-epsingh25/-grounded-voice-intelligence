"""
Gemini Live Voice Fallback API Router.

Exposes REST and WebSocket endpoints for the Gemini Live fallback voice assistant.
No secrets are exposed to the browser.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import get_config
from app.core.logging import get_logger
from app.integrations.gemini.live import GeminiLiveSession

logger = get_logger(__name__)

router = APIRouter()

# Active sessions in memory
_sessions: Dict[str, GeminiLiveSession] = {}


class MessagePayload(BaseModel):
    text: str


@router.get("/config")
async def get_gemini_live_config() -> Dict[str, Any]:
    """Return sanitized configuration for Gemini Live voice fallback."""
    config = get_config()
    return {
        "configured": bool(config.gemini.api_key),
        "model": config.gemini.live_model,
        "provider": "gemini_live",
        "role": "fallback_voice_transport",
    }


@router.post("/session/start")
async def start_gemini_session() -> Dict[str, Any]:
    """Initialize a new Gemini Live backup voice session."""
    session = GeminiLiveSession()
    _sessions[session.session_id] = session
    return {
        "session_id": session.session_id,
        "status": "connected",
        "provider": "gemini_live",
        "greeting": "Hello! I am your backup voice assistant powered by Gemini Live. I can help answer questions or qualify your business for a loan. How can I help you today?",
    }


@router.post("/session/{session_id}/message")
async def send_gemini_message(session_id: str, payload: MessagePayload) -> Dict[str, Any]:
    """Process a turn in an active Gemini Live session."""
    session = _sessions.get(session_id)
    if not session:
        # Create session if not found
        session = GeminiLiveSession(session_id=session_id)
        _sessions[session_id] = session

    return session.process_utterance(payload.text)


@router.post("/session/{session_id}/end")
async def end_gemini_session(session_id: str) -> Dict[str, Any]:
    """End a Gemini Live backup voice session."""
    session = _sessions.pop(session_id, None)
    if session:
        return session.end_session()
    return {"session_id": session_id, "status": "ended"}


@router.websocket("/ws/{session_id}")
async def gemini_live_websocket(websocket: WebSocket, session_id: str):
    """Bidirectional WebSocket for real-time Gemini Live communication."""
    await websocket.accept()
    session = _sessions.get(session_id) or GeminiLiveSession(session_id=session_id)
    _sessions[session_id] = session

    try:
        await websocket.send_json({
            "type": "ready",
            "session_id": session_id,
            "provider": "gemini_live",
            "greeting": "Connected to Gemini Live fallback voice assistant.",
        })

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                text = data.get("text", "")
                result = session.process_utterance(text)
                await websocket.send_json({"type": "turn_response", **result})
            elif msg_type == "end":
                await websocket.send_json({"type": "session_ended", "session_id": session_id})
                break

    except WebSocketDisconnect:
        logger.info(f"Gemini Live WebSocket disconnected for session {session_id}")
    finally:
        _sessions.pop(session_id, None)
