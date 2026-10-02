# Production Improvement Plan

This document outlines the strategic engineering roadmap to transition the AI Engineer Assessment prototype into an enterprise-grade, high-availability production platform.

---

## 1. Roadmap Horizons (NOW / NEXT / LATER)

```
┌───────────────────────────────┐
│              NOW              │
│    24-Hour Prototype State    │
│  - FastAPI + in-memory store  │
│  - 1.0x Real-time audio replay│
│  - Heuristic language detector│
│  - 153 passing unit tests     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│             NEXT              │
│   Short Hardening (Weeks 1-4) │
│  - Managed Qdrant vector DB   │
│  - PostgreSQL metadata store  │
│  - Live Vapi/Deepgram carrier │
│  - Redis state & pub/sub      │
│  - JWT Auth & Rate Limiting   │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│             LATER             │
│   Enterprise Scale (Months 2+)│
│  - Kafka / RabbitMQ pipelines │
│  - Horizontal worker pods     │
│  - Acoustic accent datasets   │
│  - SOC2 / HIPAA / PII audit   │
│  - Multi-region active-active │
└───────────────────────────────┘
```

---

## 2. Detailed Technical Improvements

### Horizon 1: NOW (Current Prototype State)
- **Architecture**: Single-process Python 3.14 FastAPI backend serving REST, WebSockets, and static frontend interfaces.
- **Knowledge Base**: Hybrid dense (cosine) + sparse (BM25) search operating over in-memory document chunk indices.
- **Voice Platform**: Vapi integration builders (`build_philippines_assistant`, `build_indonesia_assistant`), deterministic qualification state machine, and custom KB endpoint `/kb/search`.
- **Audio Intelligence**: 1.0x real-time WAV replay source with drift measurement (`+96.36ms`), deterministic regex rules, stateful nudge engine with deduplication and cooldowns, and live insights dashboard (`/insights`).
- **Telemetry**: T0–T4 stage latency timestamps with P50/P95 percentile computation.

---

### Horizon 2: NEXT (Short-Term Production Hardening — Weeks 1 to 4)

#### A. Managed Vector & Metadata Storage
- **Qdrant Cloud Deployment**: Replace the local in-memory vector store with managed Qdrant clusters configured with HNSW indexing and scalar quantization.
- **PostgreSQL / SQLAlchemy**: Persist structured KB records, chunk metadata, version histories, and call session logs into a durable relational database.

#### B. Telephony & Provider Onboarding
- **Live Carrier SIP Trunks**: Connect Vapi assistants to live Twilio/Vonage SIP trunks for inbound public telephone access.
- **Live Streaming ASR**: Connect `DeepgramStreamingAdapter` to live Nova 3 WebSockets with automatic reconnection backoff.
- **TTS Redundancy**: Implement active fallback across ElevenLabs, Deepgram Aura, and OpenAI TTS-1 to mitigate third-party API outages.

#### C. Concurrency & State Decoupling
- **Redis State Store**: Move active session registries, cooldown timestamps, and active nudges from in-memory Python dictionaries to Redis keys with automatic TTL expiration.
- **Redis Pub/Sub**: Decouple WebSocket dashboard broadcasting from the core audio processing loop to prevent slow consumers from degrading pipeline latency.

#### D. Security & Governance
- **Authentication & RBAC**: Protect REST and WebSocket endpoints with JWT authentication and role-based permissions (Agent vs Supervisor vs Admin).
- **Rate Limiting**: Enforce token-bucket rate limits per IP and API token to prevent denial-of-service.
- **Automated PII Governance**: Move from regex-based PII masking to transformer-based Named Entity Recognition (e.g. Presidio) for automated redaction of sensitive customer data.

---

### Horizon 3: LATER (Enterprise Scale & High Availability — Months 2+)

#### A. Distributed Audio Streaming Pipeline
- **Edge Audio Termination**: Deploy lightweight Go/Rust audio ingestion proxies at the network edge to terminate WebRTC/RTP streams and push 500ms audio chunks into a distributed message broker (Kafka or AWS Kinesis).
- **Asynchronous Worker Pools**: Run stateless signal extraction and NLP classification workers in Kubernetes pods scaling horizontally based on queue lag.
- **Adaptive Backpressure**: Under extreme CPU spikes, automatically shed interim partial transcript processing while preserving final transcript turns and high-priority compliance alerts.

#### B. Acoustic & Multilingual Benchmarking
- **Field-Recorded Regional Speech Datasets**: Collect acoustic speech recordings for Indonesian regional dialects (Surabaya/East Java, Sundanese/West Java, Medan/North Sumatra) and Philippine provincial accents (Cebuano/Ilocano English) to calculate empirical Word Error Rates (WER).
- **Model Fine-Tuning**: Fine-tune domain-specific Whisper or Deepgram acoustic models on automotive finance and bancassurance terminology.

#### C. Observability, Compliance & SOC2
- **Distributed Tracing**: Instrument OpenTelemetry across audio chunk arrival, ASR transcription, signal extraction, and WebSocket delivery for end-to-end distributed tracing.
- **Prometheus & Grafana**: Export metrics for buffer queue depths, dropped audio chunks, P50/P95/P99 pipeline latencies, and active agent nudges.
- **Audit Logging & Retention**: Enforce immutable write-once-read-many (WORM) audit trails for compliance disclosures and automated data deletion policies conforming to GDPR, CCPA, and Philippine Data Privacy Act regulations.
