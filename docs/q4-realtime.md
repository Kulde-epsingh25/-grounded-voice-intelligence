# Q4: Live Call Insights & Real-Time Nudges

## 1. Realtime Architecture

The Q4 real-time call intelligence pipeline continuously processes audio while a call is actively underway, extracting behavioral signals and delivering actionable agent nudges to a live supervisor/agent dashboard before the conversation concludes.

```
                 ┌────────────────────────────────┐
                 │          CALL AUDIO            │
                 │   Live Stream / WAV Replay     │
                 └───────────────┬────────────────┘
                                 │
                         real-time chunks (500ms)
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │     Audio Ingestion Source     │
                 │   - LiveAudioSource (bounded)  │
                 │   - WAVReplaySource (1.0x)     │
                 └───────────────┬────────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │         Streaming ASR          │
                 │   - Deepgram Nova 3 WebSocket  │
                 │   - SimulatedAudioASR (test)   │
                 │   - Partials & Finals          │
                 └───────────────┬────────────────┘
                                 │
                     incremental transcript events
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │    Signal Extraction Engine    │
                 │   - Rolling Context Window     │
                 │   - Deterministic Regex Rules  │
                 │   - Semantic Topic/Shift State │
                 └───────────────┬────────────────┘
                                 │
       ┌─────────────┬───────────┼───────────┬─────────────┐
       ▼             ▼           ▼           ▼             ▼
  Compliance    Missed Opp   Frustration  Risk / Pay    Callback
  Gap Alert     (Cross-Sell) Alert        Difficulty    Need
       └─────────────┴───────────┼───────────┴─────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │          Nudge Engine          │
                 │   - Confidence Gate (>= 0.70)  │
                 │   - Duplicate Suppression      │
                 │   - Cooldown Windows (15–30s)  │
                 │   - Priority (HIGH/MED/LOW)    │
                 │   - Auto-Expiry (45s TTL)      │
                 └───────────────┬────────────────┘
                                 │
                     WebSocket JSON broadcast
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │         Live Dashboard         │
                 │   - Incremental Transcript     │
                 │   - Active Signals & Nudges    │
                 │   - Latencies (T0..T4, P50/P95)│
                 └────────────────────────────────┘
```

---

## 2. Streaming Audio Methods & Operational Modes

To accommodate real-world deployment alongside offline testing without fabricating live telephony results, three operational modes are implemented:

| Mode | Ingestion Mechanism | ASR Engine | Verification Status | Target Use Case |
|------|---------------------|------------|---------------------|-----------------|
| **MODE A** | `LiveAudioSource` (WebRTC/WS stream) | Deepgram Nova 3 WebSocket | **IMPLEMENTED — CONFIG VALIDATED** | Live telephone or web calling interface |
| **MODE B** | `WAVReplaySource` (1.0x real-time chunks) | `SimulatedAudioASR` / Deepgram | **TESTED WITH REAL AUDIO REPLAY** | Real-time audio timing & drift benchmarking |
| **MODE C** | Timestamped transcript events | `TranscriptReplayASR` | **TESTED (DETERMINISTIC UNIT SUITE)** | Unit testing, signal rules & CI regression |

*Important: Mode C is strictly confined to deterministic unit tests and is never presented as an actual audio demonstration.*

---

## 3. Streaming ASR Configuration

- **Provider**: **Deepgram Nova 3** Streaming WebSocket API.
- **Provider Interface**: [`backend/app/realtime/asr.py`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/backend/app/realtime/asr.py) defining `StreamingASR` abstract base class.
- **Provider Adapter**: [`backend/app/integrations/asr/deepgram.py`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/backend/app/integrations/asr/deepgram.py).
- **Fallback Adapter**: `SimulatedAudioASR` ingests raw audio chunks and emits incremental partial and final transcripts synchronized with chunk timestamps, explicitly marked `"source": "SIMULATION — NOT PROVIDER ASR"`.

---

## 4. Speaker Separation

- Where provided by the streaming ASR or telephony metadata, speakers are normalized to:
  - `CUSTOMER`
  - `AGENT`
  - `UNKNOWN`
- Speaker constraints are enforced in signal rules:
  - Compliance gap rules examine `AGENT` utterances (e.g., agent asking for sensitive financial data without disclosure).
  - Cross-sell, frustration, and callback rules examine `CUSTOMER` utterances.

---

## 5. Signal Taxonomy & Extraction

Eight distinct signal types are implemented across deterministic and semantic detectors:

1. **`missed_opportunity`**: Customer mentions a second vehicle, family members, or additional business.
2. **`compliance_gap`**: Agent requests SSN, bank account, or revenue without prior recorded call disclosure, or guarantees returns.
3. **`frustration`**: Customer expresses delay, repetition ("explained three times"), or demands a supervisor.
4. **`risk`**: Customer mentions job loss, inability to pay, bankruptcy, or default.
5. **`callback_need`**: Customer states they are busy, driving, in a meeting, or requests a callback.
6. **`buying_signal`**: Customer states readiness to proceed, sign up, or request the contract.
7. **`intent`**: Customer primary goal (renewal, quote, claim, restructuring).
8. **`topic_shift`**: Progression between greeting, qualification, pricing, objection, payment, and closing.

---

## 6. Nudge Decision Logic

The `NudgeEngine` converts raw signals into actionable, agent-facing recommendations using short, directive phrasing:

- *Missed Cross-Sell*: `"Customer mentioned a second vehicle. Check multi-vehicle offer."`
- *Compliance Gap*: `"Required disclosure appears missing. Deliver mandatory call recording disclosure before proceeding."`
- *Rising Frustration*: `"Customer expressed frustration over delays. Acknowledge concern and clarify the next step."`
- *Callback Request*: `"Customer requested callback. Confirm preferred phone number and callback time."`
- *Payment Risk*: `"Customer signaled payment difficulty. Inquire about grace period or restructuring options."`

---

## 7. Suppression & Noise Controls

The nudge engine enforces five strict controls to prevent alert fatigue:

1. **Confidence Thresholding**: Signals with `confidence < 0.70` are dropped into candidate suppression logs without emitting an active nudge.
2. **Duplicate Suppression**: If an active nudge for the same signal type is currently active on screen, redundant signals are suppressed.
3. **Cooldown Windows**: After a nudge is emitted, no identical nudge is generated for the configured duration (default: 30 seconds; compliance: 15 seconds).
4. **Priority Assignment**:
   - `HIGH`: Critical compliance gaps, severe financial default risk, high customer frustration.
   - `MEDIUM`: Customer callback request, payment difficulty, buying signals.
   - `LOW`: Cross-sell opportunities, conversational topic shifts.
5. **Auto-Expiry**: Nudges automatically expire and clear from screen after 45 seconds if not dismissed by the agent.

---

## 8. WebSocket Protocol & API Endpoints

- **WebSocket Route**: `/ws/realtime/{session_id}`
- **JSON Event Types**:
  - `session_started`: Session initialization and configuration.
  - `audio_received`: Incremental chunk sequence, duration, and timestamp.
  - `transcript_partial`: Unstable interim ASR transcript.
  - `transcript_final`: Committed final transcript turn with confidence and speaker.
  - `signal_detected`: Behavioral trigger, evidence snippet, and severity.
  - `nudge_created`: Active coaching prompt, priority, and expiry.
  - `nudge_suppressed`: Log of filtered candidates (low confidence or cooldown).
  - `nudge_expired`: Removal of expired cues.
  - `latency_update`: Real-time measurement of T0–T4 pipeline stages.
  - `session_completed`: End-of-stream summary and P50/P95 latencies.

---

## 9. Live Insights Dashboard

Located at `frontend/insights/index.html` (served at `http://localhost:8000/insights`):
- **Call Status Header**: Session ID, mode (Live vs Replay), duration counter, and WebSocket connection status.
- **Live Transcript Panel**: Auto-scrolling feed differentiating agent and customer utterances, with partial and final states.
- **Active Signals Stream**: Extracted signals with rule names and confidence percentages.
- **Actionable Nudge Cards**: Color-coded badges (`HIGH` red, `MEDIUM` amber, `LOW` green) with countdown timers.
- **Real-Time Latency Gauges**: Instantaneous display of End-to-End, ASR, Signal, and Nudge latencies alongside running P50 and P95 percentiles.

---

## 10. Latency Instrumentation (T0 to T4)

Every event tracks five explicit timestamps:
- **T0**: Audio chunk ingress timestamp.
- **T1**: Transcript produced by ASR.
- **T2**: Signal extracted from transcript event.
- **T3**: Nudge evaluated and created by NudgeEngine.
- **T4**: Event dispatched via WebSocket to client.

---

## 11. Measured Latency & Percentiles

Measured on local 1.0x real-time audio replay (`evidence/q4/latency_results.json`):

| Pipeline Stage | Interval | Typical Latency (ms) | Notes |
|----------------|----------|----------------------|-------|
| **ASR Processing** | T1 - T0 | ~50–120 ms | Local simulated buffer; 250–500ms in live Deepgram Nova 3 |
| **Signal Extraction** | T2 - T1 | < 2 ms | Deterministic regex and context indexing |
| **Nudge Decision** | T3 - T2 | < 1 ms | In-memory deduplication and cooldown checks |
| **WebSocket Delivery** | T4 - T3 | < 2 ms | Local loopback transport |
| **Total End-to-End** | T4 - T0 | **~55–125 ms** | Sub-second delivery well before conversational turn ends |

---

## 12. False-Positive Evaluation Results

Evaluated on 28 labelled benchmark utterances (`data/eval/q4_signals/cases.json`):
- **Total Cases**: 28
- **True Positives (TP)**: 20
- **True Negatives (TN)**: 7
- **False Positives (FP)**: 1 (Case `CASE-NEU-03` triggered a topic shift on standard commercial tier inquiry)
- **False Negatives (FN)**: 0
- **Precision**: **95.2%**
- **Recall**: **100.0%**
- **False Positive Rate (FPR)**: **12.5%**
- **F1 Score**: **97.6%**

---

## 13. Noisy Audio Test & Suppression Verification

- **Test Fixture**: `SCENARIO D — NOISY AMBIGUOUS SUPPRESSION` in `scripts/replay_transcript.py`.
- **Condition**: Audio crackle and garbled speech: `"mumble... maybe another... car... crackle"` with degraded confidence (0.45).
- **Result**: Filtered by the confidence gate (`confidence < 0.70`). Zero false nudges emitted to the agent; logged under suppression metrics.

---

## 14. Known Limitations

1. **Live Provider Telephony Audio**: The repository has verified end-to-end real-time replay at 1.0x speed using genuine 16kHz PCM audio files with drift measurement (`108.66ms` drift). However, live external SIP/PSTN carrier calls have not been connected due to absent telephony gateway credentials.
2. **Single-Node In-Memory State**: Nudge deduplication state and active sessions are stored in memory. In multi-server deployments, this should be backed by Redis.

---

## 15. 10x Scale Summary

At 10x concurrency (10–25 streams), the pipeline requires offloading CPU regex matching from the main Python `asyncio` event loop to a background thread pool, decoupling dashboard fan-out via Redis Pub/Sub, and utilizing bounded queues with backpressure to drop interim partials during load spikes. (See full analysis in [`docs/q4-scale-analysis.md`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/docs/q4-scale-analysis.md)).
