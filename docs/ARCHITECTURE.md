# Architecture

## System Overview

This system transforms unstructured business data into a structured, searchable
knowledge base that powers voice agents, multilingual conversation bots, and
real-time call intelligence — all connected through a shared retrieval layer.

## High-Level Architecture

```
┌─────────────────────────────┐
│       BUSINESS SOURCES      │
│   PDF  DOCX  XLSX  CSV  HTML│
│   tables / PII / duplicates │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      KB INGESTION (Q2)      │
│  extraction → cleaning →    │
│  dedup → terminology →      │
│  PII → validation           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      STRUCTURED KB (Q2)     │
│  JSON records + metadata    │
│  taxonomy + versioning      │
│  source lineage             │
└──────────────┬──────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
  Dense Vectors    Sparse Index
  (OpenAI)         (BM25/Qdrant)
       │               │
       └───────┬───────┘
               ▼
        Hybrid Fusion
               ▼
          Reranker
               ▼
       Confidence Gate
          /         \
    grounded      abstain
     answer
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
 Q1 Voice    Q3 Voice    RAG API
 Agent       Agents      (POST /kb/search)
   │           │
   └─────┬─────┘
         ▼
    CALL EVENTS
         │
         ▼
   Q4 STREAMING
   ┌─────┼─────┐
   ▼     ▼     ▼
 intent risk  opportunity
   └─────┼─────┘
         ▼
   NUDGE ENGINE
         ▼
   WebSocket → Dashboard
```

## Component Architecture

### Q2: Knowledge Base Pipeline

```
Source Registry → Type Detection → Extraction → Validation
    → Cleaning → Deduplication → Terminology Normalization
    → PII Protection → Structured Records → Chunking
    → Embedding → Qdrant Indexing
```

**Key contracts:**
- `extract(source) -> ExtractedDocument`
- `clean(document) -> CleanDocument`
- `protect(document) -> ProtectedDocument`
- `store(records) -> None`

### Q2: Retrieval Layer

```
Query → Normalization → Metadata Filters
    → Dense Search ─┐
                     ├→ Fusion → Rerank → Confidence Gate → Citations
    → Sparse Search ─┘
```

**Key contract:**
- `retrieve(query, filters=None, top_k=5) -> RetrievalResult`
- `POST /kb/search` — Voice KB endpoint

### Q1: Voice Agent (Completed)

```
Caller (Browser / Vapi Web SDK)
     │
     ▼
Vapi Voice Platform
     ├── Custom KB: POST /kb/search ──► Q2 Hybrid Retrieval (BM25 + Dense Vectors)
     │                                     │
     │                                     ▼
     │                                 Confidence Gate (>= 0.60) → Citations / Safe Fallback
     │
     └── Tool Webhook: POST /api/v1/vapi/webhook
           ├── evaluate_qualification_tool ──► Deterministic Rules Engine (rules.py)
           │                                      ├── Missing field detection
           │                                      ├── Tier evaluation (Starter/Growth/Premium/Enterprise)
           │                                      └── Absolute eligibility & Manual Review gates
           ├── search_knowledge_tool ───────► Q2 Retrieval pipeline with source citations
           ├── create_lead_tool ────────────► Idempotent Lead Service (leads.py)
           └── escalate_to_human_tool ──────► Human Escalation Dispatcher
```

**Key contracts:**
- `evaluate_qualification(state) -> QualificationResult` (Deterministic rules)
- `POST /kb/search` — Vapi custom KB search endpoint
- `POST /api/v1/vapi/webhook` — Vapi server-side tool call dispatch
- `POST /api/v1/leads` — Lead management and inspection endpoint
- `GET /voice/` — Browser test interface for voice calls

### Q3: Localized Voice Agents (Completed)

```
Base Voice Agent (Q1 State & Webhooks)
    │
    ▼
BaseLocalizedAgent (agent.py)
    ├── Philippines Market (philippines.py):
    │     ├── Bancassurance / Life Insurance
    │     ├── Languages: English, Filipino/Tagalog, Taglish
    │     ├── Register: Respectful Consultative (po/opo particles)
    │     └── Insurance Terminology (premium, policy, beneficiary, rider, lapse, coverage)
    │
    └── Indonesia Market (indonesia.py):
          ├── Multifinance / Consumer Finance
          ├── Languages: Formal Bahasa (Bapak/Ibu), Colloquial Bahasa (Kak), Mixed Loanwords
          ├── Register: Professional Empathetic vs Conversational Fintech
          └── Finance Terminology (cicilan, tenor, denda, DP, jatuh tempo, angsuran, pembiayaan)

Shared Components:
    ├── MarketConfig & LanguageConfig (models.py)
    ├── TerminologyDictionary with two-pass variant resolution (terminology.py)
    ├── Heuristic Language & Register Detector (language.py)
    ├── Safe Localized Fallback Policy preserving caller language/register (fallback.py)
    ├── Vapi Multilingual Assistant Builders with Deepgram Nova 3 (assistant.py)
    ├── ElevenLabs Multilingual v2 TTS abstraction (backend/app/integrations/tts/)
    └── Q2 Retrieval Integration with market/sector/language filters (/kb/search)
```

### Q4: Real-Time Insights & Nudges (Completed)

```
Audio Source (Live Audio Stream or 1.0x WAV Replay)
     │
     ▼ (500ms chunks)
Streaming ASR (Deepgram Nova 3 WS / SimulatedAudioASR)
     │
     ▼ (Incremental partial & final transcripts)
Signal Extraction Engine (Rolling Context Window)
     ├── Deterministic Regex Rules (cross-sell, compliance, callback, frustration, risk)
     └── Semantic State Triggers (topic shift, intent)
     │
     ▼ (Extracted Signals)
Nudge Engine (Fatigue & Noise Controls)
     ├── Confidence Gate (>= 0.70)
     ├── Duplicate Suppression
     ├── Cooldown Windows (15s–30s)
     ├── Priority Hierarchy (HIGH, MEDIUM, LOW)
     └── Auto-Expiry (45s TTL)
     │
     ▼ (Actionable Coaching Prompts)
Latency Instrumentation & WebSocket Broadcaster (T0..T4 timestamps)
     │
     ▼ (ws://localhost:8000/ws/realtime/{session_id})
Live Insights Dashboard (frontend/insights/index.html)
     ├── Live Transcript Feed
     ├── Active Signals & Nudges
     └── P50 / P95 Latency Percentiles
```

**Key contracts:**
- `AudioSource.stream() -> AsyncIterator[AudioChunk]`
- `StreamingASR.receive_events() -> AsyncIterator[TranscriptEvent]`
- `SignalExtractor.process_event(event) -> List[Signal]`
- `NudgeEngine.process(signal, session_id) -> Optional[Nudge]`
- `LatencyTracker.get_summary() -> Dict[str, dict]` (P50/P95)
- `WS /ws/realtime/{session_id}` (Real-time agent/supervisor dashboard stream)
- `process_transcript(event) -> list[Nudge]`

## Data Flow

```
Business Data → Q2 Ingestion → Structured KB → Qdrant

User Query → Q2 Retrieval → Grounded Answer + Citation

Voice Call → Q1/Q3 Agent → Q2 KB Search → Grounded Response

Call Audio → Q4 Stream → ASR → Signals → Nudges → Dashboard
```

## Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend | Python 3.11+ / FastAPI | Async, typed, WebSocket native |
| Structured metadata | SQLite | Zero-config, sufficient for prototype |
| Vector DB | Qdrant | Hybrid search, metadata filtering |
| Extraction | Modular loaders (Unstructured-compatible) | Multi-format support |
| PII | Presidio + custom regex/rules | Deterministic + domain-specific |
| LLM | OpenAI API | Structured outputs, embeddings |
| Embeddings | OpenAI embeddings | Consistent with LLM provider |
| Voice | Vapi | Custom KB endpoint, Web SDK |
| Streaming STT | Deepgram | Low-latency streaming ASR |
| TTS | ElevenLabs-compatible | Multilingual voice support |
| Frontend | Minimal vanilla JS | No framework overhead |
| Realtime | FastAPI WebSocket | Native, no extra backend |
| Container | Docker Compose | Single-command dev environment |
| Public endpoint | Cloudflare Quick Tunnel | Zero-config public URL |
| Testing | pytest | Standard Python testing |

## Trust Boundaries

1. **Business truth lives in Q2 KB only.** Q1 and Q3 consume knowledge; they do not become competing knowledge stores.
2. **Confidence gate:** No retrieval evidence → no answer. The system abstains rather than hallucinating.
3. **Rules engine vs LLM:** LLM extracts fields, rules engine evaluates. Business decisions are deterministic.
4. **PII boundary:** Raw PII never appears in logs, responses, or external API calls.
5. **Secret boundary:** All credentials from environment variables. Never committed. Client code only receives public keys.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health check |
| `/kb/search` | POST | Vapi custom KB search endpoint |
| `/api/v1/kb/search` | POST | REST standard KB retrieval |
| `/api/v1/vapi/webhook` | POST | Vapi server tool-calls webhook |
| `/api/v1/leads` | GET/POST | Lead inspection and creation |
| `/api/v1/leads/{lead_id}` | GET | Fetch single lead record |
| `/voice` | GET | Browser voice testing interface |
| `/realtime/stream` | WebSocket | Q4 live audio streaming |
| `/realtime/events` | WebSocket | Q4 nudge/event delivery |
