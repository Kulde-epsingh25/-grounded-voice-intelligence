# 8-to-10 Minute Technical Walkthrough Demo Script

This script provides an exact time-stamped walkthrough for recording or presenting the AI Engineer Assessment submission.

---

## Verification Level Disclosure (Mandatory Presenter Guidance)

Before presenting, make these explicit distinctions to the evaluator:
- **DEMONSTRATED LIVE**: Local FastAPI server, Q2 retrieval `/kb/search`, deterministic qualification rules engine, Q4 1.0x real-time audio chunk replay, real timing drift measurement, WebSocket delivery, and live agent insights dashboard (`/insights`).
- **SIMULATED**: Multi-turn call traces for Q1 and Q3 generated via the agent state machine runner, accurately labeled `"call_type": "SIMULATION — NOT LIVE CALL"` in all evidence files.
- **CONFIGURED ONLY**: Deepgram Nova 3 multilingual transcriber and ElevenLabs Multilingual v2 voice presets (production configuration builders generated in `config/`, ready for live API keys).
- **TEST MANIFEST ONLY**: Indonesian regional accent acoustic test cases (Surabaya, Sundanese, Medan) with exact phonetic transcripts and concept mappings, clearly marked `TEST CASE PREPARED — AUDIO NOT YET AVAILABLE`.

---

## Walkthrough Breakdown (Target: 8–10 Minutes)

### 00:00 – 00:45 | 1. The Business Problem & Objectives
- **Key Talking Points**:
  - Financial services call centers handle high-stakes customer interactions (commercial loans, bancassurance, consumer multifinance) where compliance, speed, and accuracy are critical.
  - LLMs hallucinate financial rules and lack cultural and regulatory nuance.
  - Traditional post-call analytics arrive too late to rescue lost deals or prevent compliance breaches.
  - **Our Solution**: A unified system combining deterministic business rules, source-grounded hybrid retrieval (Q2), multilingual conversational localization for Philippines and Indonesia (Q3), and an incremental real-time call intelligence engine delivering actionable nudges while the call is still running (Q4).

---

### 00:45 – 02:00 | 2. System Architecture & Boundaries
- **Action**: Open [`docs/diagrams/system_architecture.md`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/docs/diagrams/system_architecture.md) in Markdown preview.
- **Key Talking Points**:
  - Show the 4-stage pipeline: Business Data -> Structured KB -> Voice Agents -> Call Stream -> Live Nudges.
  - Emphasize the core architectural boundary: **The LLM is NEVER the source of business truth.**
  - Business truth comes strictly from deterministic code (`rules.py`) and verified Q2 documents.

---

### 02:00 – 03:30 | 3. Q2 Ingestion, Hybrid Retrieval & Citations
- **Action**: Run retrieval evaluation in terminal:
  ```powershell
  python scripts/eval_retrieval.py
  ```
- **Action**: Send a sample query to the running API via PowerShell:
  ```powershell
  curl.exe -X POST http://localhost:8000/kb/search -H "Content-Type: application/json" -d '{\"query\": \"What are the minimum revenue and year requirements for a commercial loan?\"}'
  ```
- **Key Talking Points**:
  - Point out Reciprocal Rank Fusion (RRF) combining sparse BM25 and dense embeddings.
  - Show the confidence score (> 0.60 gate).
  - Highlight the grounded citation format: `[Source: commercial_loan_policy, Chunk: 0]`.
  - Explain the safe abstention mechanism on out-of-scope queries (e.g. lottery, cryptocurrency).

---

### 03:30 – 05:00 | 4. Q1 Knowledge-Grounded Voice Agent
- **Action**: Open browser to [http://localhost:8000/voice](http://localhost:8000/voice).
- **Action**: Show [`evidence/q1/qualification_results.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/q1/qualification_results.json).
- **Key Talking Points**:
  - Explain the deterministic qualification rules (`Starter`, `Growth`, `Premium`, `Enterprise`).
  - Walk through how objection handling calls `/kb/search` directly to retrieve policy clauses rather than hallucinating answers.
  - Review the 5 canonical test scenarios (cooperative qualification, objection handling, ambiguous amount clarification, out-of-scope abstention, human escalation).
  - Note transparently: *Call evidence currently consists of full conversational simulation traces while awaiting live telephony carrier connection.*

---

### 05:00 – 06:15 | 5. Q3 Multilingual Localization (PH & ID)
- **Action**: Show [`docs/q3-localization.md`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/docs/q3-localization.md) and [`backend/app/localization/philippines.py`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/backend/app/localization/philippines.py).
- **Key Talking Points**:
  - **Localization is NOT literal translation**: Demonstrate natural Taglish code-switching with respectful particles (`po`/`opo`) and natural loanwords (`grace period`, `policy lapse`).
  - Demonstrate Indonesia Multifinance domain terminology: `cicilan`, `tenor`, `denda`, `DP`, `jatuh tempo`, and register shifts (`Bapak/Ibu` vs `Kak`).
  - Highlight the Localized Fallback Policy: The bot **never** accidentally reverts to English during unexpected turns or knowledge gaps.
  - Review the prepared regional accent test suite for Surabaya, Sundanese, and Medan dialects.

---

### 06:15 – 07:45 | 6. Q4 Real-Time Audio Replay & Live Nudges (Highlight Demo)
- **Action 1**: Open the Live Insights Dashboard in browser: [http://localhost:8000/insights](http://localhost:8000/insights).
- **Action 2**: Run the 1.0x real-time audio replay in PowerShell:
  ```powershell
  python scripts/replay_audio.py data/audio/synthetic_call_sample.wav
  ```
- **Key Talking Points**:
  - Watch the dashboard populate turn-by-turn *while the audio is streaming*.
  - Show the audio pacing at genuine 1.0x speed with only 96.36ms of scheduling drift over 8 seconds.
  - Point out the active nudges appearing on screen:
    - Missed cross-sell alert when caller mentions "another vehicle".
    - Compliance disclosure alert when sensitive data is requested without prior recorded-line notice.
  - Explain the 5 fatigue suppression controls: Confidence thresholding (<0.70 dropped), duplicate suppression, 30s cooldown windows, priority tagging (`HIGH`, `MEDIUM`, `LOW`), and 45s auto-expiry.

---

### 07:45 – 08:30 | 7. Measurable Metrics & Evaluation Results
- **Action**: Run the Q4 false-positive evaluation script:
  ```powershell
  python scripts/eval_q4.py
  ```
- **Key Talking Points**:
  - Review the confusion matrix: 20 TP, 7 TN, 1 FP, 0 FN across 28 labelled benchmark cases.
  - Highlight 95.2% Precision and 100.0% Recall.
  - Transparently explain the single False Positive (`CASE-NEU-03` triggered a topic shift on commercial tier inquiry).
  - Review latency instrumentation: End-to-end processing takes ~65–115ms, proving coaching cues arrive in sub-second time.

---

### 08:30 – 09:15 | 8. Failure Handling & Edge Cases
- **Action**: Run the 4 deterministic scenarios:
  ```powershell
  python scripts/replay_transcript.py
  ```
- **Key Talking Points**:
  - Show Scenario C (Rising frustration: *"I've explained this three times..."* -> triggers High Priority de-escalation cue).
  - Show Scenario D (Noisy/ambiguous speech: *"mumble... maybe another... car"* -> low confidence suppresses false alert).
  - Emphasize that the system rejects noisy inputs rather than creating distraction for the agent.

---

### 09:15 – 10:00 | 9. Limitations & Production Improvement Plan
- **Action**: Open [`docs/PRODUCTION_PLAN.md`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/docs/PRODUCTION_PLAN.md).
- **Key Talking Points**:
  - Honest disclosure of current prototype limitations: in-memory vector store instead of managed Qdrant; simulated call traces instead of live PSTN audio recordings; simulated audio ASR instead of live Deepgram WebSocket streaming.
  - Outline the clear 3-horizon production roadmap:
    - **NOW**: Working end-to-end prototype, 153 passing tests, verifiable evidence.
    - **NEXT**: Managed Qdrant, live Deepgram/Vapi carrier onboarding, Redis-backed session state.
    - **LATER**: Horizontal worker autoscaling, audio backpressure, full PII governance and SOC2 compliance.
