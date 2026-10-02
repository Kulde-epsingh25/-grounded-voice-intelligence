"""
AI Engineer Assessment — Realtime Session Pipeline Orchestrator.

Glues audio ingestion, ASR streaming, signal extraction, nudge generation,
latency instrumentation, and event broadcasting into a unified incremental pipeline.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from app.core.logging import get_logger
from app.realtime.asr import StreamingASR
from app.realtime.latency import LatencyTracker
from app.realtime.models import (
    AudioChunk,
    LatencyMeasurement,
    Nudge,
    RealtimeSession,
    SessionMode,
    SessionStatus,
    Signal,
    TranscriptEvent,
)
from app.realtime.nudge_engine import NudgeEngine
from app.realtime.signals import SignalExtractor
from app.realtime.streaming import AudioSource

logger = get_logger(__name__)

EventCallback = Callable[[dict], Coroutine[None, None, None]]


class RealtimeCallSession:
    """
    Orchestrates an active real-time call session.
    
    Streams chunks, invokes incremental ASR, detects signals,
    decides nudges, measures latencies, and emits events to listeners.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        call_id: Optional[str] = None,
        mode: SessionMode = SessionMode.LIVE,
        audio_source: Optional[AudioSource] = None,
        asr_engine: Optional[StreamingASR] = None,
    ):
        self.session_id = session_id or f"sess_{uuid4().hex[:12]}"
        self.call_id = call_id or f"call_{uuid4().hex[:8]}"
        self.session = RealtimeSession(
            session_id=self.session_id,
            call_id=self.call_id,
            mode=mode,
            status=SessionStatus.CREATED,
        )

        self.audio_source = audio_source
        self.asr_engine = asr_engine
        self.signal_extractor = SignalExtractor()
        self.nudge_engine = NudgeEngine()
        self.latency_tracker = LatencyTracker()

        self._event_listeners: List[EventCallback] = []
        self._running_task: Optional[asyncio.Task] = None
        self._stopped = False
        self._transcripts: List[TranscriptEvent] = []
        self._signals: List[Signal] = []
        self._nudges: List[Nudge] = []

    def add_listener(self, callback: EventCallback) -> None:
        self._event_listeners.append(callback)

    def remove_listener(self, callback: EventCallback) -> None:
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    async def broadcast_event(self, event_type: str, data: dict) -> None:
        """Deliver an event to all attached WebSocket or logging listeners."""
        payload = {
            "session_id": self.session_id,
            "call_id": self.call_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        for listener in list(self._event_listeners):
            try:
                await listener(payload)
            except Exception as e:
                logger.warning(f"Error in realtime event listener: {e}")

    async def start(self) -> None:
        """Start streaming session."""
        self.session.status = SessionStatus.RUNNING
        await self.broadcast_event("session_started", {
            "mode": self.session.mode.value,
            "started_at": self.session.started_at.isoformat(),
        })

        if self.asr_engine:
            await self.asr_engine.start(self.session_id)

        # Launch background audio ingestion and ASR processing
        self._running_task = asyncio.create_task(self._run_pipeline())

    async def _run_pipeline(self) -> None:
        """Main processing loop streaming audio and handling transcript events."""
        try:
            # Task 1: Stream audio chunks into ASR
            audio_feeder = asyncio.create_task(self._feed_audio_to_asr())
            # Task 2: Consume transcript events from ASR
            asr_consumer = asyncio.create_task(self._consume_asr_events())

            await asyncio.gather(audio_feeder, asr_consumer)
            self.session.status = SessionStatus.COMPLETED
            await self.broadcast_event("session_completed", {
                "chunk_count": self.session.chunk_count,
                "duration_ms": self.session.duration_ms,
                "latency_summary": self.latency_tracker.get_summary(),
            })
        except Exception as e:
            logger.error(f"Pipeline failure in session {self.session_id}: {e}")
            self.session.status = SessionStatus.FAILED
            await self.broadcast_event("error", {"error": str(e)})

    async def _feed_audio_to_asr(self) -> None:
        if not self.audio_source or not self.asr_engine:
            return

        async for chunk in self.audio_source.stream():
            if self._stopped:
                break
            t0 = time.time()
            self.session.chunk_count += 1
            self.session.duration_ms += chunk.duration_ms

            await self.broadcast_event("audio_received", {
                "sequence": chunk.sequence,
                "timestamp": chunk.timestamp,
                "duration_ms": chunk.duration_ms,
            })

            await self.asr_engine.send_audio(chunk)

        if self.asr_engine:
            await self.asr_engine.close()

    async def _consume_asr_events(self) -> None:
        if not self.asr_engine:
            return

        async for transcript_event in self.asr_engine.receive_events():
            if self._stopped:
                break
            t1 = time.time()
            self._transcripts.append(transcript_event)

            # Broadcast transcript event
            event_name = "transcript_final" if transcript_event.is_final else "transcript_partial"
            await self.broadcast_event(event_name, {
                "chunk_sequence": transcript_event.chunk_sequence,
                "timestamp": transcript_event.timestamp,
                "speaker": transcript_event.speaker.value,
                "text": transcript_event.text,
                "is_final": transcript_event.is_final,
                "confidence": transcript_event.confidence,
                "source": transcript_event.source,
            })

            # Process signals
            t2 = time.time()
            signals = self.signal_extractor.process_event(transcript_event)
            for sig in signals:
                self._signals.append(sig)
                await self.broadcast_event("signal_detected", {
                    "signal_id": sig.signal_id,
                    "type": sig.type.value,
                    "confidence": sig.confidence,
                    "speaker": sig.speaker.value,
                    "evidence_text": sig.evidence_text,
                    "severity": sig.severity,
                })

                # Process nudges
                t3 = time.time()
                nudge = self.nudge_engine.process(sig, self.session_id, current_time=t3)
                if nudge:
                    self._nudges.append(nudge)
                    t4 = time.time()
                    await self.broadcast_event("nudge_created", {
                        "nudge_id": nudge.nudge_id,
                        "type": nudge.type.value,
                        "priority": nudge.priority.value,
                        "message": nudge.message,
                        "confidence": nudge.confidence,
                        "created_at": nudge.created_at,
                        "expires_at": nudge.expires_at,
                    })

                    # Record latency measurement
                    meas = LatencyMeasurement(
                        event_id=sig.signal_id,
                        t0_audio_received=transcript_event.timestamp,
                        t1_transcript_available=t1,
                        t2_signal_detected=t2,
                        t3_nudge_generated=t3,
                        t4_delivered=t4,
                    )
                    self.latency_tracker.record(meas)
                    await self.broadcast_event("latency_update", {
                        "event_id": sig.signal_id,
                        "end_to_end_ms": meas.end_to_end_ms,
                        "asr_latency_ms": meas.asr_latency_ms,
                        "signal_latency_ms": meas.signal_latency_ms,
                        "nudge_latency_ms": meas.nudge_latency_ms,
                    })

    async def stop(self) -> None:
        self._stopped = True
        if self.audio_source:
            await self.audio_source.stop()
        if self.asr_engine:
            await self.asr_engine.close()
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
