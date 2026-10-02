"""
AI Engineer Assessment — Realtime WebSocket and REST API.

Provides WebSocket streaming endpoint for live dashboard fanout and REST endpoints
for session lifecycle, audio chunk submission, and latency stats inspection.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.realtime.models import AudioChunk, SessionMode, SessionStatus
from app.realtime.session import RealtimeCallSession

logger = get_logger(__name__)

router = APIRouter()

# Global registry of active sessions
ACTIVE_SESSIONS: Dict[str, RealtimeCallSession] = {}
# WebSocket connections keyed by session_id
SESSION_SOCKETS: Dict[str, List[WebSocket]] = {}


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    call_id: Optional[str] = None
    mode: SessionMode = SessionMode.LIVE
    language: str = "en"
    market: str = "US"


class AudioChunkInput(BaseModel):
    sequence: int
    timestamp: float
    duration_ms: float = 500.0
    sample_rate: int = 16000
    channels: int = 1
    encoding: str = "linear16"
    payload_b64: Optional[str] = None


@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> dict:
    session = RealtimeCallSession(
        session_id=request.session_id,
        call_id=request.call_id,
        mode=request.mode,
    )
    ACTIVE_SESSIONS[session.session_id] = session
    SESSION_SOCKETS[session.session_id] = []

    # Attach broadcaster to push to all active WebSockets
    async def _ws_broadcaster(event: dict) -> None:
        sockets = SESSION_SOCKETS.get(session.session_id, [])
        for ws in list(sockets):
            try:
                await ws.send_json(event)
            except Exception:
                pass

    session.add_listener(_ws_broadcaster)

    return {
        "session_id": session.session_id,
        "call_id": session.call_id,
        "mode": session.session.mode.value,
        "status": session.session.status.value,
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "call_id": session.call_id,
        "mode": session.session.mode.value,
        "status": session.session.status.value,
        "chunk_count": session.session.chunk_count,
        "duration_ms": session.session.duration_ms,
        "active_nudges": [n.model_dump() for n in session.nudge_engine.active_nudges],
        "suppressed_nudges_count": session.nudge_engine.suppressed_count,
    }


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str) -> dict:
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "latency_summary": session.latency_tracker.get_summary(),
        "transcripts_count": len(session._transcripts),
        "signals_count": len(session._signals),
        "nudges_count": len(session._nudges),
        "suppressed_count": session.nudge_engine.suppressed_count,
    }


@router.websocket("/ws/{session_id}")
@router.websocket("/ws/realtime/{session_id}")
async def realtime_websocket(websocket: WebSocket, session_id: str):
    """
    Bidirectional WebSocket connection delivering live audio events, transcripts,
    signals, nudges, and latency metrics to the insights dashboard.
    """
    await websocket.accept()

    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        # Auto-create if not yet explicitly initialized
        session = RealtimeCallSession(session_id=session_id, mode=SessionMode.LIVE)
        ACTIVE_SESSIONS[session_id] = session
        SESSION_SOCKETS[session_id] = []

        async def _ws_broadcaster(event: dict) -> None:
            sockets = SESSION_SOCKETS.get(session_id, [])
            for ws in list(sockets):
                try:
                    await ws.send_json(event)
                except Exception:
                    pass

        session.add_listener(_ws_broadcaster)

    if session_id not in SESSION_SOCKETS:
        SESSION_SOCKETS[session_id] = []
    SESSION_SOCKETS[session_id].append(websocket)

    # Send initial snapshot
    await websocket.send_json({
        "event_type": "session_snapshot",
        "session_id": session.session_id,
        "status": session.session.status.value,
        "mode": session.session.mode.value,
        "active_nudges": [n.model_dump() for n in session.nudge_engine.active_nudges],
        "latency_summary": session.latency_tracker.get_summary(),
    })

    try:
        while True:
            # Keep socket alive or receive client acknowledgments
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from session {session_id}")
    finally:
        if session_id in SESSION_SOCKETS and websocket in SESSION_SOCKETS[session_id]:
            SESSION_SOCKETS[session_id].remove(websocket)
