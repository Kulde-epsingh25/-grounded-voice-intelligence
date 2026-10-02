"""
Tests for WAVReplaySource and replay timing.
"""

import asyncio
import io
import math
import struct
import wave
from app.realtime.replay import WAVReplaySource


def _create_test_wav_bytes(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        total_samples = int(duration_s * sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            val = int(math.sin(2 * math.pi * 440 * (i / sample_rate)) * 10000)
            frames.extend(struct.pack("<h", val))
        w.writeframes(frames)
    return buf.getvalue()


def test_wav_replay_chunk_sequencing_and_metadata():
    async def _test():
        wav_bytes = _create_test_wav_bytes(duration_s=1.0)
        source = WAVReplaySource(wav_input=wav_bytes, chunk_duration_ms=250.0, speed=100.0)

        chunks = []
        async for chunk in source.stream():
            chunks.append(chunk)

        # 1.0s / 0.25s = 4 chunks
        assert len(chunks) == 4
        for idx, c in enumerate(chunks):
            assert c.sequence == idx
            assert c.sample_rate == 16000
            assert c.encoding == "linear16"
            assert len(c.payload) > 0

    asyncio.run(_test())


def test_wav_replay_timing_metrics():
    async def _test():
        wav_bytes = _create_test_wav_bytes(duration_s=0.5)
        source = WAVReplaySource(wav_input=wav_bytes, chunk_duration_ms=250.0, speed=50.0)

        async for _ in source.stream():
            pass

        assert source.total_duration_ms == 500.0
        assert source.expected_replay_time_ms == 10.0
        assert source.actual_elapsed_ms > 0
        assert isinstance(source.replay_drift_ms, float)

    asyncio.run(_test())
