# Technical Decisions Log

Each decision records: Problem → Decision → Reason → Alternative Considered → Tradeoff

---

## DEC-001: Backend Framework — Python + FastAPI

- **Problem:** Need an async web framework supporting REST, WebSocket, and typed models.
- **Decision:** Python 3.11+ with FastAPI.
- **Reason:** Native async, Pydantic integration, WebSocket support, excellent for prototyping with production patterns. Covers Q1 webhooks, Q2 API, Q4 WebSocket without introducing separate services.
- **Alternative:** Flask, Django, Node.js/Express.
- **Tradeoff:** FastAPI is less mature than Django for large projects, but we don't need Django's ORM or admin. Flask lacks native async and Pydantic integration.

---

## DEC-002: Structured Metadata Store — SQLite

- **Problem:** Need persistent storage for source registry, ingestion metadata, and evaluation results.
- **Decision:** SQLite via Python's built-in `sqlite3` or `aiosqlite`.
- **Reason:** Zero configuration, no external process, sufficient for single-node prototype. Avoids adding PostgreSQL container and connection management complexity.
- **Alternative:** PostgreSQL, JSON files.
- **Tradeoff:** No concurrent writes, no network access. Acceptable for assessment scope. JSON files lack querying capability.

---

## DEC-003: Vector Database — Qdrant

- **Problem:** Need vector storage with metadata filtering and hybrid retrieval.
- **Decision:** Qdrant (Docker container).
- **Reason:** Supports dense vectors, sparse/lexical retrieval, metadata filtering, and hybrid queries. Official docs recommend evaluating dense/sparse legs separately and adding reranking for precision.
- **Alternative:** Chroma, Pinecone, Weaviate, FAISS.
- **Tradeoff:** Requires Docker container, but Docker Compose handles this. Chroma is simpler but lacks hybrid search maturity. Pinecone requires cloud account.

---

## DEC-004: Document Extraction — Modular Loaders

- **Problem:** Need to extract text from PDF, DOCX, XLSX, CSV, HTML with fallback handling.
- **Decision:** Modular loader abstraction with format-specific adapters. Compatible with Unstructured-style partitioning but not tightly coupled.
- **Reason:** Assessment requires multi-format extraction with failure handling. Abstraction lets us swap implementations without changing downstream code.
- **Alternative:** Single library (Unstructured only), manual parsing.
- **Tradeoff:** More code to maintain, but isolation prevents vendor lock-in and makes testing easier.

---

## DEC-005: PII Protection — Presidio + Custom Rules

- **Problem:** Assessment requires PII detection and protection. Must not rely solely on LLM.
- **Decision:** Microsoft Presidio for entity recognition, supplemented by custom regex for email, phone, and domain-specific identifiers.
- **Reason:** Deterministic detection without API calls. Custom rules handle domain-specific patterns (policy IDs, account numbers). Presidio provides named-entity recognition.
- **Alternative:** LLM-only, AWS Comprehend, Google DLP.
- **Tradeoff:** Presidio's NER may miss contextual PII. Acceptable because we supplement with custom rules and document limitations.

---

## DEC-006: LLM Provider — OpenAI API

- **Problem:** Need LLM for structured extraction, semantic signals, and conversation.
- **Decision:** OpenAI API (GPT-4o / GPT-4o-mini).
- **Reason:** Structured Outputs support for typed extraction. Embeddings API for vectors. Well-documented. Vapi integration.
- **Alternative:** Anthropic, Google, open-source models.
- **Tradeoff:** API cost and latency. Acceptable for assessment prototype. Model behind interface for future swapping.

---

## DEC-007: Embeddings — OpenAI Embeddings

- **Problem:** Need dense vectors for semantic retrieval.
- **Decision:** OpenAI text-embedding-3-small (or configurable).
- **Reason:** Consistent with LLM provider. Good quality-to-cost ratio. Model configurable via environment variable.
- **Alternative:** Cohere, local sentence-transformers.
- **Tradeoff:** API dependency. Local models would eliminate API calls but add GPU requirements.

---

## DEC-008: Voice Platform — Vapi

- **Problem:** Need voice interface with custom KB, tool calling, and recording.
- **Decision:** Vapi with Web SDK for browser-based calls.
- **Reason:** Supports custom KB endpoints (our retrieval backend), server-side tools, call recording, and transcripts. Web SDK avoids phone infrastructure.
- **Alternative:** Twilio + custom ASR, Retell.ai, Bland.ai.
- **Tradeoff:** Platform dependency. But Vapi handles telephony complexity and provides the recording/transcript evidence the assessment requires.

---

## DEC-009: Streaming ASR — Deepgram

- **Problem:** Q4 requires real-time streaming transcription with latency measurement.
- **Decision:** Deepgram streaming API.
- **Reason:** Low-latency streaming with interim results. Supports diarization. Latency documentation explicitly covers P50/P95 measurement methodology.
- **Alternative:** Google Speech-to-Text, AssemblyAI, Whisper.
- **Tradeoff:** API cost. Whisper is free but not streaming-native.

---

## DEC-010: TTS — ElevenLabs-Compatible

- **Problem:** Q3 requires native Filipino and Indonesian TTS.
- **Decision:** ElevenLabs (supports Filipino/Tagalog and Indonesian).
- **Reason:** Multi-language support including required markets. Vapi integration.
- **Alternative:** Google TTS, Azure TTS, OpenAI TTS.
- **Tradeoff:** Quality varies by language. Will document compromises per market.

---

## DEC-011: Realtime Delivery — FastAPI WebSocket

- **Problem:** Q4 needs real-time nudge delivery to a dashboard.
- **Decision:** FastAPI native WebSocket.
- **Reason:** No additional backend service. FastAPI supports WebSocket natively. Sufficient for single-client prototype.
- **Alternative:** Socket.IO, Redis Pub/Sub, Server-Sent Events.
- **Tradeoff:** No built-in scaling. Acceptable for demo. SSE is simpler but doesn't support bidirectional communication.

---

## DEC-012: Containerization — Docker Compose

- **Problem:** Need reproducible development environment with Qdrant.
- **Decision:** Docker Compose for local development.
- **Reason:** Single `docker compose up` starts all services. No Kubernetes complexity.
- **Alternative:** Kubernetes, manual service management.
- **Tradeoff:** Docker required on host. Assessment doesn't require cloud deployment.

---

## DEC-013: Frontend — Minimal Vanilla JS

- **Problem:** Need minimal UI for voice demo and Q4 dashboard.
- **Decision:** Vanilla HTML/CSS/JS. No React/Vue framework.
- **Reason:** Assessment says "prioritize a reliable core workflow over unnecessary features or visual polish." Framework adds build complexity without assessment value.
- **Alternative:** React/Vite, Next.js.
- **Tradeoff:** No component reuse. Acceptable for two simple pages.

---

## DEC-014: Public Demo Endpoint — Cloudflare Quick Tunnel

- **Problem:** Vapi webhooks need a public URL to reach our local FastAPI.
- **Decision:** Cloudflare Quick Tunnel (trycloudflare.com).
- **Reason:** Zero-config, no account required, creates temporary public URL. Suitable for development/demo.
- **Alternative:** ngrok, Tailscale Funnel.
- **Tradeoff:** Temporary URL, not for production. Ngrok requires account for stable URLs.

---

## DEC-015: Business Rules Separation

- **Problem:** Assessment evaluates qualification logic. LLM decisions are non-deterministic.
- **Decision:** LLM extracts structured fields → deterministic rules engine evaluates eligibility.
- **Reason:** Reproducible, testable, auditable business decisions. LLM handles natural language; rules handle policy.
- **Alternative:** Let LLM decide everything.
- **Tradeoff:** More code. But prevents the LLM from inventing eligibility criteria.

---

## DEC-016: Confidence-Gated Retrieval

- **Problem:** Assessment explicitly penalizes hallucinated answers and disconnected KB.
- **Decision:** If retrieval confidence is below threshold, return explicit abstention.
- **Reason:** Directly addresses assessment rejection condition: "hallucinated answers." Safe fallback is better than fabricated answers.
- **Alternative:** Always attempt an answer.
- **Tradeoff:** May refuse to answer some legitimate questions. Preferable to hallucination.

---

## DEC-017: Audio Replay Strategy for Q4

- **Problem:** Q4 requires real-time processing, but building second telephony stack is impractical in 24 hours.
- **Decision:** Replay recorded call audio at real-time speed in chunks.
- **Reason:** Assessment explicitly allows "live call audio or a recording replayed at real-time speed in chunks."
- **Alternative:** Live telephony integration.
- **Tradeoff:** Not truly live. But satisfies the requirement and allows accurate latency measurement.

---

## DEC-018: Hybrid Retrieval (Dense + BM25) with RRF and Fine-Grained Reranking

- **Problem:** Pure dense vector search often misses exact numerical values, specific interest rates, and loan tier names, while pure BM25 lacks semantic understanding.
- **Decision:** Hybrid retrieval combining dense vector embeddings with sparse BM25 lexical indexing, fused via Reciprocal Rank Fusion (RRF) and reranked using a multi-signal reranker (subphrase matches, section heading alignment, numeric entity presence).
- **Reason:** Provides both semantic generalization and pinpoint precision on financial numbers/policies. Qdrant architecture explicitly advises evaluating dense and sparse legs separately.
- **Alternative:** Pure vector embeddings, pure BM25 search.
- **Tradeoff:** Computation of both vector cosine distance and BM25 index scores; mitigated by lightweight in-memory storage and sub-millisecond retrieval execution (<2ms).

---

## DEC-019: Dual Interface for Retrieval (Standard REST + Vapi Custom KB)

- **Problem:** Q1 voice bot (Vapi) uses a custom knowledge-base protocol passing conversation messages, while standard web/eval clients query with string queries and structured filters.
- **Decision:** Dual routing with `/api/v1/kb/search` (standard schema) and `/kb/search` (Vapi messages array payload alias) backed by the same confidence-gated hybrid retrieval engine.
- **Reason:** Enables plug-and-play voice integration directly with Vapi's custom knowledge base webhook configuration without glue proxies.
- **Alternative:** Separate proxy microservice or translating within voice prompt.
- **Tradeoff:** Extra routing parsing logic in `api/kb.py`.

