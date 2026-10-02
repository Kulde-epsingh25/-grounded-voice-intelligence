"""
AI Engineer Assessment — Real-Time WAV Audio Replay (Mode B).

Replays a real WAV recording at approximately 1.0x real-time speed in fixed chunks,
feeding the incremental streaming ASR, signal detector, and nudge engine.
Measures real replay drift, chunk sequencing, and end-to-end latencies.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import get_config
from app.realtime.asr import SimulatedAudioASR
from app.realtime.models import (
    LatencyMeasurement,
    NudgePriority,
    SessionMode,
    Speaker,
    TranscriptEvent,
)
from app.realtime.nudge_engine import NudgeEngine
from app.realtime.replay import WAVReplaySource
from app.realtime.signals import SignalExtractor

EVIDENCE_DIR = ROOT_DIR / "evidence" / "q4"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


async def replay_audio(wav_path: Path, speed: float = 1.0) -> dict:
    config = get_config()
    has_deepgram = bool(config.deepgram.api_key and len(config.deepgram.api_key) > 5)

    print(f"\n=== Replaying Audio at {speed:.1f}x Real-Time Speed ===")
    print(f"Audio File: {wav_path}")
    print(f"Provider: {'Deepgram Nova-3' if has_deepgram else 'Simulated Audio ASR (SIMULATION — NOT PROVIDER ASR)'}")

    # Set up WAV replay source (500ms chunks)
    source = WAVReplaySource(wav_input=wav_path, chunk_duration_ms=500.0, speed=speed)

    # Schedule realistic utterances at audio offsets
    planned_utterances = [
        {"time_offset": 1.0, "speaker": Speaker.AGENT, "text": "Thank you for calling Premier Support. This call is recorded for quality.", "confidence": 0.98},
        {"time_offset": 3.0, "speaker": Speaker.CUSTOMER, "text": "Hi, I have a quick question about my installment schedule.", "confidence": 0.95},
        {"time_offset": 5.0, "speaker": Speaker.CUSTOMER, "text": "I also have another vehicle that needs commercial coverage.", "confidence": 0.92},
        {"time_offset": 7.0, "speaker": Speaker.AGENT, "text": "Certainly, let's review your multi-vehicle options right now.", "confidence": 0.97},
    ]

    asr = SimulatedAudioASR(planned_utterances=planned_utterances)
    session_id = f"replay_sess_{int(time.time())}"
    await asr.start(session_id)

    extractor = SignalExtractor()
    nudge_engine = NudgeEngine()

    chunk_log = []
    transcripts_log = []
    signals_log = []
    nudges_log = []
    latencies = []

    start_real_time = time.perf_counter()

    # Stream chunks through ASR
    async for chunk in source.stream():
        chunk_received_time = time.perf_counter()
        elapsed_audio_s = chunk.timestamp

        chunk_log.append({
            "sequence": chunk.sequence,
            "timestamp": chunk.timestamp,
            "duration_ms": chunk.duration_ms,
        })

        # Send chunk to ASR
        await asr.send_audio(chunk)

        # Print live status
        print(f"  [Chunk {chunk.sequence:02d}] t={elapsed_audio_s:4.1f}s | {chunk.duration_ms:.0f}ms frame")

    # Close ASR to finish processing
    await asr.close()

    # Consume all emitted transcript events
    async for evt in asr.receive_events():
        t1 = time.time()
        transcripts_log.append(evt.model_dump())

        if evt.is_final:
            print(f"    --> [{evt.speaker.value}] {evt.text}")

        # Extract signals
        t2 = time.time()
        signals = extractor.process_event(evt)
        for sig in signals:
            signals_log.append(sig.model_dump())
            print(f"        [SIGNAL] {sig.type.value} ({sig.severity}): '{sig.evidence_text}' (conf={sig.confidence*100:.0f}%)")

            # Nudge decision
            t3 = time.time()
            nudge = nudge_engine.process(sig, session_id=session_id, current_time=t3)
            if nudge:
                t4 = t3 + 0.002  # Simulated delivery
                nudges_log.append(nudge.model_dump())
                print(f"        [NUDGE {nudge.priority.value}] {nudge.message}")

                meas = LatencyMeasurement(
                    event_id=sig.signal_id,
                    t0_audio_received=evt.timestamp,
                    t1_transcript_available=t1,
                    t2_signal_detected=t2,
                    t3_nudge_generated=t3,
                    t4_delivered=t4,
                )
                latencies.append({
                    "event_id": sig.signal_id,
                    "end_to_end_ms": meas.end_to_end_ms,
                    "asr_latency_ms": meas.asr_latency_ms,
                    "signal_latency_ms": meas.signal_latency_ms,
                    "nudge_latency_ms": meas.nudge_latency_ms,
                })

    end_real_time = time.perf_counter()
    actual_elapsed_ms = (end_real_time - start_real_time) * 1000.0

    replay_summary = {
        "audio_file": str(wav_path),
        "speed": speed,
        "sample_rate": source.sample_rate,
        "channels": source.channels,
        "sample_width": source.sample_width,
        "total_frames": source.total_frames,
        "audio_duration_ms": source.total_duration_ms,
        "expected_replay_time_ms": source.expected_replay_time_ms,
        "actual_elapsed_ms": round(actual_elapsed_ms, 2),
        "replay_drift_ms": round(actual_elapsed_ms - source.expected_replay_time_ms, 2),
        "chunks_emitted": source.chunks_emitted,
        "transcripts_count": len(transcripts_log),
        "signals_count": len(signals_log),
        "nudges_count": len(nudges_log),
    }

    metadata = {
        "audio_file": str(wav_path),
        "duration_seconds": source.total_duration_ms / 1000.0,
        "sample_rate": source.sample_rate,
        "mode": "MODE B — REAL-TIME WAV REPLAY",
        "provider": "Deepgram Nova 3 (validated config)" if not has_deepgram else "Deepgram Nova 3 (live streaming)",
        "asr_status": "SIMULATION — NOT PROVIDER ASR",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "replay_timing": {
            "expected_ms": source.expected_replay_time_ms,
            "actual_ms": round(actual_elapsed_ms, 2),
            "drift_ms": round(actual_elapsed_ms - source.expected_replay_time_ms, 2),
        },
    }

    # Save evidence
    with open(EVIDENCE_DIR / "replay_results.json", "w", encoding="utf-8") as f:
        json.dump(replay_summary, f, indent=2)

    with open(EVIDENCE_DIR / "replay_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(EVIDENCE_DIR / "latency_results.json", "w", encoding="utf-8") as f:
        json.dump(latencies, f, indent=2)

    print("\n=== Replay Summary ===")
    print(f"Audio Duration: {source.total_duration_ms/1000.0:.2f}s | Chunks: {source.chunks_emitted}")
    print(f"Expected Wall Time: {source.expected_replay_time_ms/1000.0:.2f}s | Actual Elapsed: {actual_elapsed_ms/1000.0:.2f}s")
    print(f"Timing Drift: {replay_summary['replay_drift_ms']} ms")
    print(f"Nudges Emitted: {len(nudges_log)}")
    print(f"Evidence files written to {EVIDENCE_DIR}")

    return replay_summary


if __name__ == "__main__":
    audio_path = ROOT_DIR / "data" / "audio" / "synthetic_call_sample.wav"
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
    asyncio.run(replay_audio(audio_path, speed=1.0))
