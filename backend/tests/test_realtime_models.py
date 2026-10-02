"""
Tests for Realtime domain models (AudioChunk, TranscriptEvent, Signal, Nudge, Latency).
"""

from app.realtime.models import (
    AudioChunk,
    LatencyMeasurement,
    Nudge,
    NudgePriority,
    NudgeStatus,
    RealtimeSession,
    SessionMode,
    SessionStatus,
    Signal,
    SignalType,
    Speaker,
    TranscriptEvent,
)


def test_audio_chunk_creation():
    chunk = AudioChunk(
        sequence=1,
        timestamp=0.5,
        duration_ms=500.0,
        sample_rate=16000,
        channels=1,
        encoding="linear16",
        payload=b"\x00\x00" * 8000,
    )
    assert chunk.sequence == 1
    assert chunk.timestamp == 0.5
    assert chunk.duration_ms == 500.0
    assert len(chunk.payload) == 16000


def test_transcript_event():
    evt = TranscriptEvent(
        session_id="s1",
        chunk_sequence=2,
        timestamp=1.0,
        text="Hello world",
        is_final=True,
        speaker=Speaker.CUSTOMER,
        confidence=0.95,
    )
    assert evt.is_final is True
    assert evt.speaker == Speaker.CUSTOMER
    assert evt.confidence == 0.95


def test_signal_and_nudge_models():
    sig = Signal(
        signal_id="sig_1",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=5.0,
        confidence=0.88,
        speaker=Speaker.CUSTOMER,
        evidence_text="second car",
        severity="medium",
    )
    assert sig.type == SignalType.MISSED_OPPORTUNITY

    nudge = Nudge(
        nudge_id="n1",
        session_id="s1",
        type=SignalType.MISSED_OPPORTUNITY,
        priority=NudgePriority.MEDIUM,
        message="Check multi-vehicle offer",
        confidence=0.88,
        created_at=5.0,
        expires_at=50.0,
        source_signal="sig_1",
        evidence="second car",
        status=NudgeStatus.ACTIVE,
    )
    assert nudge.priority == NudgePriority.MEDIUM
    assert nudge.status == NudgeStatus.ACTIVE


def test_latency_measurement_calculations():
    meas = LatencyMeasurement(
        event_id="e1",
        t0_audio_received=1.000,
        t1_transcript_available=1.120,
        t2_signal_detected=1.135,
        t3_nudge_generated=1.140,
        t4_delivered=1.145,
    )
    assert round(meas.asr_latency_ms, 1) == 120.0
    assert round(meas.signal_latency_ms, 1) == 15.0
    assert round(meas.nudge_latency_ms, 1) == 5.0
    assert round(meas.delivery_latency_ms, 1) == 5.0
    assert round(meas.end_to_end_ms, 1) == 145.0
