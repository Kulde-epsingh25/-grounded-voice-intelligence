# AI Engineer Assessment: Production-Style Voice & Real-Time Intelligence

[![Tests](https://img.shields.io/badge/tests-153%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## 1. Executive Summary

This repository delivers a unified, production-style architecture for knowledge-grounded voice agents, culturally localized multilingual bots, and streaming call intelligence. Built during a focused 24-hour sprint, it prioritizes **architectural honesty, strict grounding boundaries, sub-second streaming latency, and alert fatigue suppression** over unverified claims.

All four core assessment areas are fully implemented, accompanied by **153 passing automated tests**, structured evidence manifests, live browser interfaces, and reproducible evaluation harnesses.

---

## 2. Problem Statement

Financial services voice interactions (commercial lending, bancassurance, consumer leasing) face three critical engineering bottlenecks:
1. **Generative Hallucinations**: Standard LLMs invent loan eligibility terms, interest rates, and compliance guarantees when answering caller questions.
2. **Robotic Translation**: Word-for-word translation creates culturally alienating voice bots that fail in bilingual, high-context markets like the Philippines (Taglish) and Indonesia (Bahasa with register shifts).
3. **Delayed Call Intelligence**: Traditional speech analytics process audio only *after* the call disconnects—too late to rescue a lost cross-sell opportunity or correct a critical compliance omission.

---

## 3. Assessment Mapping

| Assessment Requirement | Module | Implementation | Evidence Artifact | Verification Status |
|------------------------|--------|----------------|-------------------|---------------------|
| **Q1: Grounded Voice Agent** | `backend/app/agents/` | Deterministic rules engine + Q2 search | `evidence/q1/calls/` | **PARTIAL — SIMULATION ONLY** |
| **Q2: Production Knowledge Base** | `backend/app/kb/` | Ingestion, PII scrubbing, hybrid RRF | `evidence/q2/retrieval_results.json` | **PASS (PROTOTYPE STORE)** |
| **Q3: Multilingual Voice Bots** | `backend/app/localization/` | PH Bancassurance & ID Multifinance | `evidence/q3/` | **PARTIAL — SIMULATION ONLY** |
| **Q4: Real-Time Call Intelligence** | `backend/app/realtime/` | 1.0x WAV chunk streaming + Nudges | `evidence/q4/replay_results.json` | **PASS (REAL WAV REPLAY)** |

*For complete requirement-by-requirement traceability, see [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).*

---

## 4. System Architecture

```text
BUSINESS SOURCES (PDF, DOCX, XLSX, CSV, HTML)
                     │
                     ▼
             KB INGESTION (Q2)
  Extraction → Cleaning → Dedup → Terminology → PII Scrubbing
                     │
                     ▼
          STRUCTURED KB RECORDS & CHUNKS
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    Sparse BM25 Index       Dense Embeddings
         │                       │
         └───────────┬───────────┘
                     ▼
         Hybrid Fusion (RRF) & Reranking
                     │
                     ▼
       Confidence Gate (Threshold >= 0.60)
             /               \
       Grounded Citations     Safe Fallback Abstain
             │
   ┌─────────┴─────────┐
   ▼                   ▼
Q1 Voice Agent     Q3 Localized Agents
(Commercial Loans) (PH & ID Banking)
   │                   │
   └─────────┬─────────┘
             ▼
     CALL AUDIO STREAM (Live WebRTC / 1.0x WAV Replay)
             │
             ▼ (500ms Audio Chunks)
     STREAMING ASR (Deepgram Nova 3 WebSocket)
             │
             ▼ (Incremental Partials & Finals)
     SIGNAL EXTRACTION (Deterministic Rules + Context)
  Cross-Sell | Compliance Gap | Frustration | Risk | Callback
             │
             ▼
     NUDGE ENGINE (Fatigue & Noise Controls)
  Confidence (>=0.70) | Deduplication | Cooldown | Expiry
             │
             ▼ (WebSocket Event Hub)
     LIVE DASHBOARD (/insights)
  Live Transcript | Active Nudges | Latency Gauges
```

*For dedicated Mermaid flowcharts, see [`docs/diagrams/system_architecture.md`](docs/diagrams/system_architecture.md).*

---

## 4.1 Provider Strategy & Fallback Architecture

The system implements a **primary-provider + automatic fallback-provider architecture** across all conversational modalities.

### Primary Providers (Preferred Production Path)
- **Vapi**: Primary voice orchestration platform & telephony Web SDK
- **OpenAI**: Primary LLM where currently utilized (`gpt-4o-mini`, `text-embedding-3-small`)
- **Deepgram**: Primary streaming ASR (`Nova-3` multilingual)
- **ElevenLabs**: Primary neural TTS (`eleven_multilingual_v2`)

### Fallback Providers (Resilience & Free-Tier Insurance)
- **Gemini API / Gemini Live**: Backup voice transport, text reasoning, and multimodal ASR/TTS
- **Groq**: Secondary ultra-low-latency LLM fallback (`llama-3.3-70b-versatile`)
- **OpenRouter**: Tertiary open-model routing fallback
- **Hugging Face Local Models**: Edge sovereign fallback (`openai/whisper-large-v3-turbo` for ASR, `facebook/mms-tts-tgl` & `mms-tts-ind` for TTS)

### Fallback Activation Principles
The fallback layer activates **only** when:
- the primary provider is unavailable or connection times out,
- rate limits are reached (HTTP 429),
- the provider returns a temporary server error (HTTP 500, 502, 503, 504),
- or primary credentials are not configured in `.env`.

Client errors (HTTP 400), malformed payloads, and business-rule qualification disqualifications **never** trigger fallback.
Business logic, deterministic rules, hybrid knowledge base retrieval, call event auditing, and human escalation remain 100% provider-independent.

### Fallback Routing Diagram

```text
                     APPLICATION
                          |
                PROVIDER ABSTRACTION
                          |
        ┌─────────────────┼─────────────────┐
        │                 │                 │
       LLM               ASR               TTS
        │                 │                 │
   ┌────┴────┐       ┌────┴────┐       ┌────┴────┐
   │ OpenAI  │       │Deepgram │       │ Eleven  │
   │ PRIMARY │       │ PRIMARY │       │ PRIMARY │
   └────┬────┘       └────┬────┘       └────┬────┘
        │                  │                  │
        ↓                  ↓                  ↓
     Gemini             Gemini             Gemini
        ↓                  ↓                  ↓
      Groq             HF Whisper         HF MMS
        ↓
   OpenRouter
```

### Configuration Guidelines
- **Primary APIs are preferred**: When configured, all traffic flows through the primary production path.
- **Fallback APIs are optional**: The system continues working normally when fallback credentials are absent, utilizing local open models and deterministic evaluation fixtures.
- **Truthful Verification Standard**: The system explicitly reports `CONFIGURED`, `LIVE VERIFIED`, `MOCK VERIFIED`, or `LOCAL VERIFIED`.
- **Never Hard-Code Keys**: All tokens are resolved dynamically from environment variables.


---

## 5. Technology Stack

- **Backend**: Python 3.10–3.14, FastAPI, Uvicorn, Pydantic v2.
- **Retrieval & NLP**: BM25 (sparse lexical), dense vector similarity, Reciprocal Rank Fusion (RRF), regex-based PII scrubber.
- **Voice Platform Integration**: Vapi Web SDK (`@vapi-ai/web`), Vapi custom KB endpoint (`POST /kb/search`), Vapi Function Call Webhooks (`POST /api/v1/vapi/webhook`).
- **ASR & Audio Ingestion**: Deepgram Nova 3 multilingual configuration (`language: "multi"`), standard 16kHz PCM WAV chunk slicer (`WAVReplaySource`).
- **TTS Presets**: ElevenLabs Multilingual v2 abstraction (`backend/app/integrations/tts/`).
- **Frontend Interfaces**: Pure vanilla HTML5, JavaScript, and CSS (zero build-step overhead, zero node_modules dependencies).

---

## 6. Q2: Knowledge Base Data Pipeline

The Q2 pipeline converts heterogeneous raw documents into structured, searchable records:
- **Loaders**: Clean extractors for PDF, DOCX, XLSX, CSV, and HTML preserving table schemas and cell boundaries.
- **Cleaning & Dedup**: Strips navigation headers, boilerplate, and filters duplicate records via SimHash / content hashing.
- **Terminology Normalization**: Standardizes financial concepts, currencies, dates, and form labels.
- **PII Masking**: Scans and masks email addresses (`[EMAIL_REDACTED]`), phone numbers (`[PHONE_REDACTED]`), and SSNs (`[SSN_REDACTED]`).
- **Section-Aware Chunking**: Configurable 512-token chunks with 64-token overlap respecting table boundaries.
- **Hybrid Search**: Fuses dense semantic scores and BM25 sparse matching via Reciprocal Rank Fusion.
- **Confidence Gate**: Enforces a strict score threshold (0.60); ungrounded queries safely abstain with zero hallucination.

---

## 7. Q1: Knowledge-Grounded Voice Agent

- **Architectural Boundary**: The LLM is **never** the source of business truth.
- **Deterministic Rules Engine**: Commercial loan qualification evaluates four tiers (`Starter`, `Growth`, `Premium`, `Enterprise`) against business revenue, operating years, and credit scores without generative drift.
- **Grounded Objection Handling**: Objections regarding rates or document requirements query `/kb/search` directly and return verifiable citations (`[Source: commercial_loan_policy, Chunk: 0]`).
- **Browser Client**: Fully functional browser test phone interface at `http://localhost:8000/voice`.

---

## 8. Q3: Multilingual & Localized Voice Agents

Built on top of the shared core agent rather than duplicating code:
- **Philippines Bancassurance (`philippines.py`)**:
  - Focuses on grace periods, policy lapse prevention, and branch specialist endorsements.
  - Deploys natural Taglish code-switching with respectful particles (`po`/`opo`) and natural English loanwords (`grace period`, `policy lapse`).
- **Indonesia Multifinance (`indonesia.py`)**:
  - Focuses on consumer automotive and electronic financing.
  - Deploys formal (`Bapak/Ibu`) vs colloquial digital app (`Kak`) registers.
  - Standardizes retail finance loanwords: `cicilan`, `tenor`, `denda`, `DP`, `jatuh tempo`, `angsuran`.
- **Localized Fallback Policy**: The agent strictly preserves caller language and register when handling unexpected turns, preventing unintended reversion to English.

---

## 9. Q4: Real-Time Call Intelligence & Nudges

Processes audio **while the call is underway**, delivering actionable coaching cues before conversation turns conclude:
- **Streaming Ingestion**: Slices audio into 500ms chunks and paces playback at genuine 1.0x real-time speed.
- **Signal Taxonomy**: Detects missed cross-sells, compliance omissions, rising customer frustration, financial risk, and callback requests.
- **Nudge Engine**: Enforces 5 noise-reduction controls (confidence gate, duplicate suppression, 30s cooldown windows, priority tagging, and 45s auto-expiry).
- **Live Supervisor Dashboard**: Real-time WebSocket feed at `http://localhost:8000/insights`.

---

## 10. Setup Instructions

```bash
# 1. Clone & enter repository
git clone https://github.com/your-org/ai-engineer-assessment.git
cd ai-engineer-assessment

# 2. Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows PowerShell: .\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r backend/requirements.txt
```

---

## 11. Environment Variables

Copy the template:
```bash
cp .env.example .env
```

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `APP_ENV` | `development` | Application runtime environment |
| `APP_PORT` | `8000` | Port for FastAPI server |
| `RETRIEVAL_CONFIDENCE_THRESHOLD` | `0.60` | Minimum score required for grounded answers |
| `VAPI_API_KEY` | *(Optional)* | Private Vapi key for live telephone calls |
| `DEEPGRAM_API_KEY` | *(Optional)* | Deepgram API key for live streaming ASR |
| `OPENAI_API_KEY` | *(Optional)* | OpenAI API key for live GPT/embeddings |

---

## 12. Running Locally

Start the unified backend server:
```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

Endpoints:
- **Service Health Check**: `http://localhost:8000/health`
- **Q1 Voice UI**: `http://localhost:8000/voice`
- **Q4 Live Insights Dashboard**: `http://localhost:8000/insights`
- **Q2 Knowledge Base Search**: `POST http://localhost:8000/kb/search`

---

## 13. Running Tests

Run all 153 unit and integration tests:
```bash
python -m pytest backend/tests/ -v
```

---

## 14. Running KB Ingestion

To process raw document fixtures through extraction, cleaning, PII scrubbing, and chunk indexing:
```bash
python -c "from app.kb.pipeline import KnowledgeBasePipeline; KnowledgeBasePipeline().process_all()"
```

---

## 15. Running Retrieval Evaluation

Evaluate hybrid retrieval hit rate and confidence gate abstentions:
```bash
python scripts/eval_retrieval.py
```
*Output: `evidence/q2/retrieval_results.json`*

---

## 16. Running Voice Demo (Q1)

Generate the 5 canonical qualification call traces:
```bash
python scripts/generate_q1_evidence.py
```
*Output: `evidence/q1/calls/`*

---

## 17. Running Q3 Multilingual Demo

Simulate six localized conversations across Philippines and Indonesia:
```bash
python scripts/simulate_q3.py
```
*Output: `evidence/q3/`*

---

## 18. Running Q4 Real-Time Audio Replay (Highlight Demo)

Stream the 16kHz standard WAV audio file at 1.0x real-time speed in 500ms chunks, measuring clock drift and emitting live nudges:
```bash
python scripts/replay_audio.py data/audio/synthetic_call_sample.wav
```
*Output: `evidence/q4/replay_results.json`*

To run the 4 canonical deterministic scenarios:
```bash
python scripts/replay_transcript.py
```

---

## 19. Evaluation Results Summary

| Evaluation Area | Key Metric | Measured Result | Evidence Source |
|-----------------|------------|-----------------|-----------------|
| **Test Suite** | Pass Rate | **153 / 153 (100%)** | `evidence/final_test_results.json` |
| **Q2 Retrieval** | Grounded Precision | **100.0%** (5/5 queries) | `evidence/q2/retrieval_results.json` |
| **Q4 Signal Precision** | Precision | **95.2%** (20/21 alerts) | `evidence/q4/final_false_positive_audit.json` |
| **Q4 Signal Recall** | Recall | **100.0%** (20/20 targets) | `evidence/q4/final_false_positive_audit.json` |
| **Q4 Audio Pacing** | Timing Drift | **+96.36 ms** over 8.0s | `evidence/q4/replay_results.json` |
| **Pipeline Latency** | Median (P50) | **105.0 ms** | `evidence/q4/metric_reconciliation.json` |
| **Pipeline Latency** | 95th Percentile (P95) | **190.5 ms** | `evidence/q4/metric_reconciliation.json` |

---

## 20. Verifiable Evidence Directory

- [`evidence/q1/`](evidence/q1/): Call traces (`call-01.json` to `call-05.json`) and qualification outcomes.
- [`evidence/q2/`](evidence/q2/): Ingestion statistics, extraction manifests, and retrieval benchmark results.
- [`evidence/q3/`](evidence/q3/): Localized conversation traces (`philippines/` and `indonesia/`), terminology dictionaries, and regional accent manifests.
- [`evidence/q4/`](evidence/q4/): 1.0x real-time replay timing, 4 required scenarios, false-positive audit, and latency reconciliation.
- [`evidence/demo/`](evidence/demo/): Unified JSON demo manifests pointing directly to evidence files.

---

## 21. Documented Limitations

1. **Carrier Telephony Audio**: Call evidence currently consists of verified multi-turn simulation traces generated via the state machine runner. Actual live telephone recordings have not yet been produced due to absent external telephony credentials.
2. **Prototype Retrieval Backend**: Q2 hybrid search operates against a high-performance in-memory dense+BM25 store; deployment to managed Qdrant clusters is documented as the production roadmap.
3. **Regional Accent Benchmark**: Prepared phonetic manifests exist for Surabaya, Sundanese, and Medan dialects, but empirical acoustic Word Error Rate benchmarks require recorded field audio.

---

## 22. Production Improvement Plan (NOW / NEXT / LATER)

- **NOW (Prototype)**: In-memory store, 1.0x real-time WAV replay, deterministic rules, 153 passing unit tests.
- **NEXT (Weeks 1–4)**: Managed Qdrant vector cloud, PostgreSQL metadata DB, live Vapi/Deepgram carrier onboarding, Redis state and pub/sub.
- **LATER (Months 2+)**: Edge audio proxies, Kubernetes worker autoscaling, regional speech corpus fine-tuning, SOC2 / HIPAA / PII audit trails.
*(See full plan in [`docs/PRODUCTION_PLAN.md`](docs/PRODUCTION_PLAN.md)).*

---

## 23. Security & Privacy Notes

- **Zero Hardcoded Secrets**: Exhaustive audit confirmed no API tokens or private keys in source code.
- **Frontend Isolation**: Client-side JavaScript never receives private credentials.
- **Automated PII Scrubbing**: Personal identifiers are redacted before document chunking.
- **Memory Bounding**: Audio buffers use bounded queues (`maxsize=100`) to prevent memory exhaustion.
*(See complete security report in [`evidence/security_audit.md`](evidence/security_audit.md)).*
