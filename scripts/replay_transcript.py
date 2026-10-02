"""
AI Engineer Assessment — Deterministic Transcript Replay Runner (Mode C).

Simulates incremental transcript stream for unit and integration testing.
Executes the four required Q4 scenarios:
- Scenario A: Missed cross-sell
- Scenario B: Compliance gap
- Scenario C: Rising frustration
- Scenario D: Noisy / ambiguous input with suppression

MODE C MUST NEVER BE PRESENTED AS THE ACTUAL FINAL REAL-TIME AUDIO DEMO.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.realtime.models import (
    LatencyMeasurement,
    NudgePriority,
    NudgeStatus,
    SessionMode,
    SignalType,
    Speaker,
    TranscriptEvent,
)
from app.realtime.nudge_engine import NudgeEngine
from app.realtime.signals import SignalExtractor

EVIDENCE_DIR = ROOT_DIR / "evidence" / "q4"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


async def run_scenario(name: str, transcript_turns: list) -> dict:
    print(f"\n--- Running {name} ---")
    extractor = SignalExtractor()
    nudge_engine = NudgeEngine()

    timeline = []
    latencies = []

    for turn in transcript_turns:
        t0 = turn["timestamp"]
        evt = TranscriptEvent(
            session_id=f"sess_{name.lower().replace(' ', '_')}",
            chunk_sequence=turn.get("sequence", 0),
            timestamp=t0,
            text=turn["text"],
            is_final=turn.get("is_final", True),
            speaker=Speaker[turn.get("speaker", "CUSTOMER")],
            confidence=turn.get("confidence", 1.0),
            source="SIMULATION — NOT PROVIDER ASR",
        )

        t1 = t0 + 0.080  # simulated ASR latency (80ms)
        signals = extractor.process_event(evt)
        t2 = t1 + 0.015  # simulated signal latency (15ms)

        emitted_nudges = []
        for sig in signals:
            t3 = t2 + 0.005  # simulated nudge decision (5ms)
            nudge = nudge_engine.process(sig, session_id=evt.session_id, current_time=t3)
            if nudge:
                t4 = t3 + 0.010  # simulated delivery (10ms)
                emitted_nudges.append(nudge.model_dump())
                meas = LatencyMeasurement(
                    event_id=sig.signal_id,
                    t0_audio_received=t0,
                    t1_transcript_available=t1,
                    t2_signal_detected=t2,
                    t3_nudge_generated=t3,
                    t4_delivered=t4,
                )
                latencies.append(meas.end_to_end_ms)

        timeline.append({
            "timestamp": t0,
            "speaker": evt.speaker.value,
            "text": evt.text,
            "confidence": evt.confidence,
            "signals": [s.model_dump() for s in signals],
            "nudges": emitted_nudges,
        })

        status_str = f"[{evt.speaker.value}] {evt.text}"
        if emitted_nudges:
            status_str += f" -> [NUDGE {emitted_nudges[0]['priority']}] {emitted_nudges[0]['message']}"
        elif signals and not emitted_nudges:
            status_str += f" -> [SUPPRESSED SIGNAL] {signals[0].type.value} (conf={signals[0].confidence})"
        print(status_str)

    return {
        "scenario": name,
        "mode": "MODE C — TRANSCRIPT REPLAY (TEST ONLY)",
        "turns_processed": len(transcript_turns),
        "active_nudges_emitted": len([t for t in timeline if t["nudges"]]),
        "suppressed_count": nudge_engine.suppressed_count,
        "latencies_ms": latencies,
        "timeline": timeline,
    }


async def main():
    # SCENARIO A: Missed Cross-Sell
    scenario_a = [
        {"sequence": 0, "timestamp": 1.0, "speaker": "AGENT", "text": "Good morning, thank you for calling Premier Auto Insurance. This call is recorded for quality assurance."},
        {"sequence": 1, "timestamp": 3.0, "speaker": "CUSTOMER", "text": "Hi, I'm calling about my sedan policy renewal."},
        {"sequence": 2, "timestamp": 5.0, "speaker": "AGENT", "text": "I can certainly help you with your sedan policy today."},
        {"sequence": 3, "timestamp": 7.5, "speaker": "CUSTOMER", "text": "Also, I have another vehicle that I might want to add to this coverage later."},
        {"sequence": 4, "timestamp": 9.5, "speaker": "AGENT", "text": "Great, let's review your details first."},
    ]

    # SCENARIO B: Compliance Gap
    scenario_b = [
        {"sequence": 0, "timestamp": 1.0, "speaker": "AGENT", "text": "Hello, thank you for calling financing support today."},
        {"sequence": 1, "timestamp": 3.0, "speaker": "CUSTOMER", "text": "I'm interested in applying for a commercial loan."},
        {"sequence": 2, "timestamp": 5.0, "speaker": "AGENT", "text": "Please provide your social security number and annual business revenue right now."},
    ]

    # SCENARIO C: Rising Frustration
    scenario_c = [
        {"sequence": 0, "timestamp": 1.0, "speaker": "AGENT", "text": "Thank you for holding. Can you state your account number?"},
        {"sequence": 1, "timestamp": 3.0, "speaker": "CUSTOMER", "text": "I already entered it in the automated prompt."},
        {"sequence": 2, "timestamp": 5.5, "speaker": "AGENT", "text": "I understand, but our screen refreshed so I need you to repeat it."},
        {"sequence": 3, "timestamp": 8.0, "speaker": "CUSTOMER", "text": "I've explained this three times already. Why is this taking so long? Waste of my time!"},
    ]

    # SCENARIO D: Noisy / Ambiguous
    scenario_d = [
        {"sequence": 0, "timestamp": 1.0, "speaker": "AGENT", "text": "Hello, can you hear me clearly?"},
        {"sequence": 1, "timestamp": 3.0, "speaker": "CUSTOMER", "text": "mumble... maybe another... car... crackle", "confidence": 0.45},
        {"sequence": 2, "timestamp": 5.0, "speaker": "AGENT", "text": "Pardon me, the audio broke up."},
    ]

    res_a = await run_scenario("SCENARIO A — MISSED CROSS-SELL", scenario_a)
    res_b = await run_scenario("SCENARIO B — COMPLIANCE GAP", scenario_b)
    res_c = await run_scenario("SCENARIO C — RISING FRUSTRATION", scenario_c)
    res_d = await run_scenario("SCENARIO D — NOISY AMBIGUOUS SUPPRESSION", scenario_d)

    evidence = {
        "scenario_a_missed_cross_sell": res_a,
        "scenario_b_compliance_gap": res_b,
        "scenario_c_rising_frustration": res_c,
        "scenario_d_noisy_suppression": res_d,
    }

    with open(EVIDENCE_DIR / "required_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)

    with open(EVIDENCE_DIR / "nudge_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "scenario_a_nudges": res_a["active_nudges_emitted"],
            "scenario_b_nudges": res_b["active_nudges_emitted"],
            "scenario_c_nudges": res_c["active_nudges_emitted"],
            "scenario_d_nudges": res_d["active_nudges_emitted"],
            "scenario_d_suppressed": res_d["suppressed_count"],
        }, f, indent=2)

    print(f"\nAll 4 scenarios executed and saved to {EVIDENCE_DIR / 'required_scenarios.json'}")


if __name__ == "__main__":
    asyncio.run(main())
