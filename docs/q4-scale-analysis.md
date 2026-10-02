# Q4: 10x Concurrency Scale Analysis

This document analyzes system behavior, resource constraints, and architectural bottlenecks when scaling the real-time call intelligence engine from a single prototype call stream to **10x concurrent calls** (~10–25 active audio streams) and outlines the architectural migration required for production workloads.

---

## 1. Projected Concurrency Profiles (1x vs 10x)

| Metric | 1x Baseline (Prototype) | 10x Concurrency Target | Scaling Impact |
|--------|-------------------------|------------------------|----------------|
| **Active Audio Streams** | 1 stream | 10–25 streams | Audio chunk throughput: 20–50 chunks/sec (at 500ms chunk intervals) |
| **Ingress Bandwidth** | ~32 KB/s (16kHz 16-bit mono) | 320–800 KB/s | Well within typical network interfaces, but requires non-blocking socket I/O |
| **WebSocket Connections** | 1–2 client sockets | 25–50 dashboard connections | Connection management & event loop fan-out overhead |
| **ASR Streaming Sessions** | 1 session (Deepgram Nova 3) | 10–25 persistent WebSocket sessions | Rate limits & socket exhaustion on external ASR |
| **Signal Extraction Rate** | 1–2 events / second | 20–40 events / second | Regex evaluations are CPU-bound; context management requires bounds |
| **Nudge Deduplication State** | In-memory dict per session | 25 concurrent state machines | Memory scales linearly; negligible (<5MB) |
| **Latency Budget Target** | E2E < 250ms | E2E < 400ms (P95) | Event-loop contention becomes the primary source of latency jitter |

---

## 2. Component Bottlenecks at 10x Concurrency

### A. Concurrent ASR Streaming
- **Bottleneck**: Managing 10–25 full-duplex WebSocket connections to an external ASR provider (e.g. Deepgram Nova 3) within a single Python async process.
- **Risk**: Connection timeouts, socket drops during network fluctuations, and API rate limits.
- **Remediation**:
  - Implement a persistent connection pool with automatic exponential backoff reconnection.
  - Offload streaming ASR ingestion to an edge gateway or lightweight Go/Rust audio proxy that terminates raw audio and emits standardized JSON transcript events into a message broker.

### B. Single-Threaded Event Loop Contention (Python GIL)
- **Bottleneck**: In Python's standard `asyncio`, all regex signal matching, PII scanning, and JSON serialization run on the main event loop thread. A burst of 25 simultaneous final transcript events could block the loop for 20–50ms, introducing scheduling jitter in audio chunk pacing.
- **Risk**: P95 latency degradation; audio chunks delayed in memory buffers.
- **Remediation**:
  - Offload CPU-intensive regex matching and NLP classification to a thread pool executor (`loop.run_in_executor`) or process pool.
  - Split the audio ingestion pipeline from the intelligence analysis pipeline.

### C. LLM Throughput for Semantic Signals
- **Bottleneck**: If semantic signals (nuanced buying intent or topic drift) invoke LLM inference on every turn, 10 calls generating 1 final transcript every 3 seconds results in ~3.3 LLM requests/second.
- **Risk**: Token rate limiting (TPM/RPM), API latency spikes (500–1200ms), and high cost.
- **Remediation**:
  - Tiered architecture: Fast deterministic rules run synchronously in sub-millisecond time.
  - Semantic LLM evaluations only trigger when rule confidence is ambiguous (0.60–0.75) or on specific high-value customer phrases.
  - Implement speculative or batched asynchronous classification queues.

### D. WebSocket Dashboard Fan-out
- **Bottleneck**: Broadcasting every partial transcript, signal, and latency measurement to multiple agent supervisor screens using in-memory Python loops.
- **Risk**: Slow consumer blocking; if one client socket experiences high TCP window latency, it may delay message processing for other clients.
- **Remediation**:
  - Decouple dashboard fan-out via Redis Pub/Sub or a dedicated WebSocket gateway (e.g. Centrifugo or AWS API Gateway WebSocket).

---

## 3. Production Architecture Migration

```
               ┌───────────────────────────────┐
               │    Inbound Audio Streams      │
               │    (WebRTC / Telephony SIP)   │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    Edge Ingestion Proxy       │
               │    (Go / Rust / Envoy)        │
               └───────┬───────────────┬───────┘
                       │               │
       audio chunks    ▼               ▼  direct streaming
               ┌───────────────┐ ┌───────────────┐
               │  ASR Provider │ │  Local Audio  │
               │ (Deepgram WS) │ │  Buffer (S3)  │
               └───────┬───────┘ └───────────────┘
                       │
               transcript events
                       │
                       ▼
               ┌───────────────────────────────┐
               │  Message Broker (Redis/Kafka) │
               └───────┬───────────────┬───────┘
                       │               │
        ┌──────────────┴───────┐       └──────────────┐
        ▼                      ▼                      ▼
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│ Signal Worker  │     │  Nudge Engine  │     │  Dashboard WS  │
│ (Regex & NLP)  │     │ (Dedupe/State) │     │ (Pub/Sub Hub)  │
└────────────────┘     └────────────────┘     └────────────────┘
```

### Architectural Upgrades
1. **Asynchronous Task Queuing**: Use Redis Streams or RabbitMQ to decouple audio chunk ingestion from transcript processing.
2. **Worker Pool Autoscaling**: Deploy stateless signal workers in Kubernetes pods scaling horizontally based on queue depth.
3. **Backpressure & Bounded Dropping**: When CPU spikes, drop partial transcript evaluations and only process final transcripts to preserve end-to-end latency for active nudges.
4. **Distributed State Store**: Store cooldown timestamps and active nudge state in Redis with short key TTLs (e.g., 60s) rather than in-memory Python dictionaries.
5. **Observability**: Prometheus metrics for pipeline stage latencies (T0 through T4), audio buffer depth, and dropped frame counts.

---

## 4. Concluding Note on Benchmarking
*All figures in this analysis represent architectural estimations based on single-stream measurements and standard Python asyncio concurrency characteristics. No production multi-tenant load test is claimed without cluster-level empirical measurements.*
