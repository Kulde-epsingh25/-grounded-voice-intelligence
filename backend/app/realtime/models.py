"""
AI Engineer Assessment — Realtime Call Intelligence Models.

Defines domain models for streaming audio, transcripts, signals, nudges,
latency tracking, and sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionMode(str, Enum):
    LIVE = "live"
    REPLAY = "replay"
    TRANSCRIPT_TEST = "transcript_test"


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Speaker(str, Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    UNKNOWN = "UNKNOWN"


class SignalType(str, Enum):
    INTENT = "intent"
    TOPIC_SHIFT = "topic_shift"
    COMPLIANCE_GAP = "compliance_gap"
    RISK = "risk"
    FRUSTRATION = "frustration"
    BUYING_SIGNAL = "buying_signal"
    MISSED_OPPORTUNITY = "missed_opportunity"
    CALLBACK_NEED = "callback_need"


class NudgePriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NudgeStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"
    DISMISSED = "dismissed"


class AudioChunk(BaseModel):
    """Bounded audio chunk emitted during live streaming or audio replay."""
    sequence: int
    timestamp: float = Field(..., description="Timestamp in seconds from stream start")
    duration_ms: float = Field(default=500.0, description="Duration in milliseconds")
    sample_rate: int = Field(default=16000, description="Audio sample rate (Hz)")
    channels: int = Field(default=1, description="Number of channels")
    encoding: str = Field(default="linear16", description="Audio encoding: linear16, pcm, wav")
    payload: Optional[bytes] = Field(default=None, description="Raw audio bytes (bounded)")
    reference: Optional[str] = Field(default=None, description="Optional URI/file reference")


class TranscriptEvent(BaseModel):
    """Incremental transcript event received from streaming ASR."""
    session_id: str
    chunk_sequence: int
    timestamp: float
    text: str
    is_final: bool = False
    speaker: Speaker = Speaker.UNKNOWN
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    language: str = "en"
    words: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "asr"


class Signal(BaseModel):
    """Extracted behavioral or conversational signal."""
    signal_id: str
    type: SignalType
    timestamp: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    speaker: Speaker = Speaker.UNKNOWN
    evidence_text: str
    severity: str = Field(default="medium", description="low, medium, high, critical")
    source: str = Field(default="rule", description="rule or semantic")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Nudge(BaseModel):
    """Actionable agent coaching recommendation generated during the call."""
    nudge_id: str
    session_id: str
    type: SignalType
    priority: NudgePriority
    message: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: float
    expires_at: float
    cooldown_seconds: float = 30.0
    source_signal: str
    evidence: str
    status: NudgeStatus = NudgeStatus.CANDIDATE
    suppression_reason: Optional[str] = None


class LatencyMeasurement(BaseModel):
    """Point-in-time latency measurement across pipeline stages."""
    event_id: str
    t0_audio_received: float
    t1_transcript_available: float
    t2_signal_detected: Optional[float] = None
    t3_nudge_generated: Optional[float] = None
    t4_delivered: Optional[float] = None

    @property
    def asr_latency_ms(self) -> float:
        return max(0.0, (self.t1_transcript_available - self.t0_audio_received) * 1000.0)

    @property
    def signal_latency_ms(self) -> Optional[float]:
        if self.t2_signal_detected is not None:
            return max(0.0, (self.t2_signal_detected - self.t1_transcript_available) * 1000.0)
        return None

    @property
    def nudge_latency_ms(self) -> Optional[float]:
        if self.t3_nudge_generated is not None and self.t2_signal_detected is not None:
            return max(0.0, (self.t3_nudge_generated - self.t2_signal_detected) * 1000.0)
        return None

    @property
    def delivery_latency_ms(self) -> Optional[float]:
        if self.t4_delivered is not None and self.t3_nudge_generated is not None:
            return max(0.0, (self.t4_delivered - self.t3_nudge_generated) * 1000.0)
        return None

    @property
    def end_to_end_ms(self) -> float:
        final_time = self.t4_delivered or self.t3_nudge_generated or self.t2_signal_detected or self.t1_transcript_available
        return max(0.0, (final_time - self.t0_audio_received) * 1000.0)


class RealtimeSession(BaseModel):
    """Metadata tracking an active real-time call intelligence session."""
    session_id: str
    call_id: str
    mode: SessionMode = SessionMode.LIVE
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SessionStatus = SessionStatus.CREATED
    language: str = "en"
    market: str = "US"
    chunk_count: int = 0
    duration_ms: float = 0.0
