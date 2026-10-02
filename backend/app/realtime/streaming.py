"""
AI Engineer Assessment — Realtime Audio Streaming Ingestion.

Provides the AudioSource abstraction and LiveAudioSource implementation
with bounded buffering to prevent unbounded memory growth.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from app.realtime.models import AudioChunk


class AudioSource(ABC):
    """Abstract interface for all audio sources (Live, WAV Replay, Mock)."""

    @abstractmethod
    def stream(self) -> AsyncIterator[AudioChunk]:
        """Yield AudioChunks incrementally."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully terminate audio emission."""
        pass


class LiveAudioSource(AudioSource):
    """
    Live streaming audio source receiving chunks from WebRTC/WebSocket/API.
    
    Uses a bounded asyncio.Queue to ensure fixed memory footprint
    even under network bursts or downstream delays.
    """

    def __init__(self, max_queue_size: int = 100):
        self._queue: asyncio.Queue[Optional[AudioChunk]] = asyncio.Queue(maxsize=max_queue_size)
        self._stopped = False
        self._dropped_chunks = 0

    async def push_chunk(self, chunk: AudioChunk) -> bool:
        """
        Push an audio chunk into the bounded stream buffer.
        
        Returns True if accepted, False if buffer was full (dropped).
        """
        if self._stopped:
            return False

        try:
            self._queue.put_nowait(chunk)
            return True
        except asyncio.QueueFull:
            self._dropped_chunks += 1
            return False

    async def end_of_stream(self) -> None:
        """Signal that no more live chunks will arrive."""
        if not self._stopped:
            self._stopped = True
            await self._queue.put(None)

    async def stop(self) -> None:
        """Stop receiving and yield completion sentinel."""
        await self.end_of_stream()

    async def stream(self) -> AsyncIterator[AudioChunk]:
        """Asynchronously yield audio chunks as they arrive."""
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                self._queue.task_done()
                break
            yield chunk
            self._queue.task_done()

    @property
    def dropped_count(self) -> int:
        return self._dropped_chunks
