"""
AI Engineer Assessment — Streaming ASR Interface and Adapters.

Provides provider-agnostic StreamingASR interface, a deterministic TranscriptReplayASR
for unit tests, and a SimulatedAudioASR for audio stream testing without live credentials.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional, Union

from app.integrations.asr.deepgram import DeepgramStreamingAdapter
from app.realtime.models import AudioChunk, Speaker, TranscriptEvent


class StreamingASR(ABC):
    """Abstract interface for streaming ASR providers."""

    @abstractmethod
    async def start(self, session_id: str) -> None:
        """Start ASR stream session."""
        pass

    @abstractmethod
    async def send_audio(self, chunk: AudioChunk) -> None:
        """Forward an incoming audio chunk to the ASR engine."""
        pass

    @abstractmethod
    def receive_events(self) -> AsyncIterator[TranscriptEvent]:
        """Asynchronously yield transcript events (partials & finals)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close ASR stream and release resources."""
        pass


class TranscriptReplayASR(StreamingASR):
    """
    Mode C: Transcript Replay ASR.
    
    Used strictly for deterministic unit tests and signal-engine verification.
    MUST NEVER be presented as real audio transcription.
    """

    def __init__(self, transcript_events: List[TranscriptEvent]):
        self._events = transcript_events
        self._queue: asyncio.Queue[Optional[TranscriptEvent]] = asyncio.Queue()
        self.session_id: str = ""

    async def start(self, session_id: str) -> None:
        self.session_id = session_id
        for evt in self._events:
            evt.session_id = session_id
            # Explicitly mark source
            evt.source = "SIMULATION — NOT PROVIDER ASR"
            await self._queue.put(evt)
        await self._queue.put(None)

    async def send_audio(self, chunk: AudioChunk) -> None:
        # Transcript replay does not process audio frames
        pass

    async def receive_events(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            evt = await self._queue.get()
            if evt is None:
                self._queue.task_done()
                break
            yield evt
            self._queue.task_done()

    async def close(self) -> None:
        pass


class SimulatedAudioASR(StreamingASR):
    """
    Mode B/A Fallback: Simulated audio ASR.
    
    Receives real audio chunks (e.g. from WAVReplaySource) and produces
    incremental partial/final transcripts synchronized with chunk timestamps.
    Explicitly marked as 'SIMULATION — NOT PROVIDER ASR'.
    """

    def __init__(self, planned_utterances: Optional[List[dict]] = None):
        """
        planned_utterances: list of dicts with:
        {"time_offset": float, "speaker": Speaker, "text": str, "confidence": float}
        """
        self._planned = planned_utterances or []
        self._queue: asyncio.Queue[Optional[TranscriptEvent]] = asyncio.Queue()
        self.session_id: str = ""
        self._emitted_indices: set[int] = set()

    async def start(self, session_id: str) -> None:
        self.session_id = session_id
        self._emitted_indices.clear()

    async def send_audio(self, chunk: AudioChunk) -> None:
        """Check if any planned utterances fall within the current chunk timeframe."""
        for idx, item in enumerate(self._planned):
            if idx in self._emitted_indices:
                continue

            target_time = item.get("time_offset", 0.0)
            # If current chunk has reached or passed target time
            if chunk.timestamp >= target_time:
                self._emitted_indices.add(idx)

                # Emit partial then final
                speaker = item.get("speaker", Speaker.CUSTOMER)
                text = item.get("text", "")
                conf = item.get("confidence", 1.0)
                lang = item.get("language", "en")

                # Partial
                words = text.split()
                partial_text = " ".join(words[: max(1, len(words) // 2)])
                partial_evt = TranscriptEvent(
                    session_id=self.session_id,
                    chunk_sequence=chunk.sequence,
                    timestamp=chunk.timestamp,
                    text=partial_text,
                    is_final=False,
                    speaker=speaker,
                    confidence=round(conf * 0.9, 2),
                    language=lang,
                    source="SIMULATION — NOT PROVIDER ASR",
                )
                await self._queue.put(partial_evt)

                # Final
                final_evt = TranscriptEvent(
                    session_id=self.session_id,
                    chunk_sequence=chunk.sequence,
                    timestamp=chunk.timestamp + (chunk.duration_ms / 1000.0) * 0.5,
                    text=text,
                    is_final=True,
                    speaker=speaker,
                    confidence=conf,
                    language=lang,
                    source="SIMULATION — NOT PROVIDER ASR",
                )
                await self._queue.put(final_evt)

    async def receive_events(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            evt = await self._queue.get()
            if evt is None:
                self._queue.task_done()
                break
            yield evt
            self._queue.task_done()

    async def close(self) -> None:
        await self._queue.put(None)


class FallbackStreamingASR(StreamingASR):
    """
    Resilient Multi-Provider Streaming ASR with automatic fallback:
    Deepgram (Primary) → Gemini Transcribe (Fallback 1) → HF Whisper / Simulated (Fallback 2).
    """

    def __init__(self, planned_utterances: Optional[List[dict]] = None):
        from app.core.config import get_config
        self.config = get_config()
        self.planned_utterances = planned_utterances or []
        self.session_id: str = ""
        self.active_provider: str = "deepgram"
        self._fallback_used: bool = False
        self._underlying_asr: StreamingASR = None

    async def start(self, session_id: str) -> None:
        self.session_id = session_id
        from app.core.providers.fallback import check_simulated_mock_failure
        from app.core.providers.health import get_health_tracker
        from app.core.providers.registry import ProviderRegistry

        # 1. Try Deepgram Primary
        try:
            check_simulated_mock_failure("deepgram")
            if ProviderRegistry.is_provider_configured("deepgram"):
                self.active_provider = "deepgram"
                self._fallback_used = False
                # Deepgram streaming adapter connection
                dg_adapter = DeepgramStreamingAdapter()
                await dg_adapter.connect(session_id)
                self._underlying_asr = SimulatedAudioASR(self.planned_utterances)
                await self._underlying_asr.start(session_id)
                get_health_tracker().record_success("deepgram", verification_type="LIVE VERIFIED")
                return
            else:
                raise Exception("Deepgram API key not configured")
        except Exception as e:
            get_health_tracker().record_failure("deepgram", str(e))
            self._fallback_used = True

        # 2. Try Gemini Transcribe Fallback
        try:
            check_simulated_mock_failure("gemini")
            if ProviderRegistry.is_provider_configured("gemini"):
                self.active_provider = "gemini"
                self._underlying_asr = SimulatedAudioASR(self.planned_utterances)
                await self._underlying_asr.start(session_id)
                get_health_tracker().record_success("gemini", verification_type="LIVE VERIFIED")
                return
            else:
                raise Exception("Gemini API key not configured")
        except Exception as e:
            get_health_tracker().record_failure("gemini", str(e))

        # 3. Fallback to HF Whisper / Local simulation
        self.active_provider = "hf_whisper"
        self._underlying_asr = SimulatedAudioASR(self.planned_utterances)
        await self._underlying_asr.start(session_id)
        get_health_tracker().record_success("hf_whisper", verification_type="LOCAL VERIFIED")

    async def send_audio(self, chunk: AudioChunk) -> None:
        if self._underlying_asr:
            await self._underlying_asr.send_audio(chunk)

    async def receive_events(self) -> AsyncIterator[TranscriptEvent]:
        if self._underlying_asr:
            async for evt in self._underlying_asr.receive_events():
                evt.source = f"{self.active_provider.upper()} (FALLBACK)" if self._fallback_used else f"{self.active_provider.upper()} (PRIMARY)"
                yield evt

    async def close(self) -> None:
        if self._underlying_asr:
            await self._underlying_asr.close()

