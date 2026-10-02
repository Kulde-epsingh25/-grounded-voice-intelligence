"""
AI Engineer Assessment — Realtime WAV Audio Replay.

Plays back a WAV recording in fixed-duration chunks at approximately 1.0x real-time
speed, instrumenting scheduling accuracy and clock drift.
"""

from __future__ import annotations

import asyncio
import io
import time
import wave
from pathlib import Path
from typing import AsyncIterator, Optional, Union

from app.realtime.models import AudioChunk
from app.realtime.streaming import AudioSource


class WAVReplaySource(AudioSource):
    """
    Simulates real-time streaming audio ingestion by slicing a WAV file
    into fixed-size chunks and pacing emissions to 1.0x real-time speed.
    """

    def __init__(
        self,
        wav_input: Union[str, Path, bytes],
        chunk_duration_ms: float = 500.0,
        speed: float = 1.0,
    ):
        self.chunk_duration_ms = chunk_duration_ms
        self.speed = max(0.1, speed)  # default 1.0x
        self._stopped = False

        # Load WAV info
        if isinstance(wav_input, (str, Path)):
            self.file_path = str(wav_input)
            self._wav_file = wave.open(self.file_path, "rb")
        else:
            self.file_path = "memory://sample.wav"
            self._wav_file = wave.open(io.BytesIO(wav_input), "rb")

        self.sample_rate = self._wav_file.getframerate()
        self.channels = self._wav_file.getnchannels()
        self.sample_width = self._wav_file.getsampwidth()  # bytes per sample
        self.total_frames = self._wav_file.getnframes()
        self.total_duration_ms = (self.total_frames / self.sample_rate) * 1000.0

        # Calculate bytes per chunk
        self.frames_per_chunk = int((self.sample_rate * (self.chunk_duration_ms / 1000.0)))
        self.bytes_per_chunk = self.frames_per_chunk * self.channels * self.sample_width

        # Drift tracking
        self.chunks_emitted = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    async def stop(self) -> None:
        self._stopped = True
        try:
            self._wav_file.close()
        except Exception:
            pass

    async def stream(self) -> AsyncIterator[AudioChunk]:
        """
        Stream chunks at real-time paced intervals.
        """
        self.chunks_emitted = 0
        self.start_time = time.perf_counter()
        current_time_offset = 0.0

        while not self._stopped:
            raw_frames = self._wav_file.readframes(self.frames_per_chunk)
            if not raw_frames:
                break

            actual_frames = len(raw_frames) // (self.channels * self.sample_width)
            duration_ms = (actual_frames / self.sample_rate) * 1000.0

            chunk = AudioChunk(
                sequence=self.chunks_emitted,
                timestamp=round(current_time_offset / 1000.0, 3),
                duration_ms=round(duration_ms, 2),
                sample_rate=self.sample_rate,
                channels=self.channels,
                encoding="linear16" if self.sample_width == 2 else f"pcm_{self.sample_width*8}",
                payload=raw_frames,
                reference=self.file_path,
            )

            yield chunk
            self.chunks_emitted += 1
            current_time_offset += duration_ms

            # Real-time pacing: pace sleep based on chunk duration adjusted for speed
            sleep_duration = (duration_ms / 1000.0) / self.speed
            if sleep_duration > 0.001 and not self._stopped:
                await asyncio.sleep(sleep_duration)

        self.end_time = time.perf_counter()
        try:
            self._wav_file.close()
        except Exception:
            pass

    @property
    def expected_replay_time_ms(self) -> float:
        """Expected duration based on audio length divided by speed multiplier."""
        return self.total_duration_ms / self.speed

    @property
    def actual_elapsed_ms(self) -> float:
        """Actual wall-clock time taken to replay the audio stream."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000.0

    @property
    def replay_drift_ms(self) -> float:
        """Difference between actual elapsed wall time and theoretical replay time."""
        if self.start_time is None:
            return 0.0
        return self.actual_elapsed_ms - self.expected_replay_time_ms
