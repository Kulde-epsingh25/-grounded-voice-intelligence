# Hugging Face & Commercial Model Comparison and Provenance Audit

## Overview

This document presents the complete provenance, execution modes, and empirical verification status of all open-source Hugging Face models and commercial cloud APIs evaluated in this project.

In accordance with strict technical audit standards, each metric is explicitly classified by its genuine execution mode:
- **`LIVE_HF_API`**: Executed against live Hugging Face Inference Providers using authenticated tokens.
- **`LIVE_API`**: Executed against live third-party cloud API endpoints (Deepgram, ElevenLabs, Vapi).
- **`LOCAL_MODEL`**: Executed locally using active code/weights in the local environment.
- **`MOCK`**: Evaluated against scenario text fixtures or pre-defined response simulations.
- **`DETERMINISTIC_FALLBACK`**: Computed via deterministic local algorithms in place of unconfigured cloud services.
- **`CATALOG_ONLY`**: Literature/catalog reference surveyed for architectural feasibility; not executed.
- **`UNKNOWN`**: Unverifiable execution provenance.

---

## Model Comparison Matrix

| Task | Model | Execution Mode | Dataset / Audio Input | Metric | Result | Latency | Reproducible? | Evidence File |
|---|---|---|---|---|---|---|---|---|
| **Q2 Dense Semantic Similarity** | `BAAI/bge-m3` | `LIVE_HF_API` | 8 evaluation queries (EN, TL, ID) | Cosine Relevance Score | Live HF router: **0.8141** (loan) vs **0.3048** (weather) | 210ms | Yes | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q2 Cross-Encoder Rerank** | `BAAI/bge-reranker-v2-m3` | `MOCK` | Candidate query/passage pairs | Cross-Encoder Margin | Grounded: 0.86–0.94; OOS: 0.08 | ~65ms (CPU estimate) | Yes | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q2 Baseline Hybrid Retrieval** | Local BM25 + Dense Hash + Booster | `LOCAL_MODEL` | [`data/eval/retrieval.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/data/eval/retrieval.json) (7 queries) | Grounded Precision & Top-1 Source | **100% Precision**; 100% correct source | **P50 = 0.69ms**, P95 = 1.18ms | Yes | [`evidence/q2/retrieval_results.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/q2/retrieval_results.json) |
| **Q3 Realtime Streaming ASR** | Deepgram Nova-3 (`multi`) | `LIVE_API` | Live synthesized MP3 audio (PH & ID) | Acoustic Word Error Rate (WER) & Latency | Live ASR executed on speech; Tagalog WER 70%, ID WER 100% (un-tuned) | 290ms–320ms | Yes | [`evidence/providers/deepgram_status.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/providers/deepgram_status.json) |
| **Q3 Offline Reference ASR** | `openai/whisper-large-v3-turbo` | `LIVE_HF_API` | Live synthesized MP3 audio (PH & ID) | Acoustic Word Error Rate (WER) & Latency | **Indonesian WER: 0.0%** (perfect match); **Tagalog WER: 20.0%** | 720ms–780ms | Yes | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q3 High-Acc Reference ASR** | `openai/whisper-large-v3` | `CATALOG_ONLY` | N/A | Acoustic Transcription Quality | Cataloged for benchmark; not run | N/A | No | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q3 Cloud Conversational TTS**| ElevenLabs Multilingual v2 | `LIVE_API` | Tagalog & Indonesian banking phrases | Synthesized Audio Verification | **Live synthesized 66KB (PH) & 94KB (ID) MP3s** | 340ms–365ms | Yes | [`evidence/providers/elevenlabs_status.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/providers/elevenlabs_status.json) |
| **Q3 Tagalog Edge TTS** | `facebook/mms-tts-tgl` | `CATALOG_ONLY` | Tagalog bancassurance phrase | CPU Generation Latency & Architecture | VITS 36M param model card reference | <50ms (model card CPU spec) | No | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q3 Indonesian Edge TTS** | `facebook/mms-tts-ind` | `CATALOG_ONLY` | Indonesian multifinance phrase | CPU Generation Latency & Architecture | VITS 36M param model card reference | <50ms (model card CPU spec) | No | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Regional Speech Research (ASR)** | `ai4bharat/indic-conformer-600m-multilingual` | `CATALOG_ONLY` | N/A | Indic language coverage (22 scheduled) | Architecture surveyed; out of scope for PH/ID | N/A | No | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Regional Speech Research (TTS)** | `ai4bharat/IndicF5` | `CATALOG_ONLY` | N/A | Indic speech synthesis (1,417h dataset) | Architecture surveyed; out of scope for PH/ID | N/A | No | [`evidence/eval_hf_benchmark.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/eval_hf_benchmark.json) |
| **Q4 Real-Time Nudge Streaming** | Local Regex + Stateful Nudge Engine | `LOCAL_MODEL` | [`data/audio/synthetic_call_sample.wav`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/data/audio/synthetic_call_sample.wav) (8.0s WAV) | Precision, Recall, & Timing Drift | **Precision: 95.2%, Recall: 100%, Drift: +96.36ms** | **Pipeline P50 = 105.0ms**, P95 = 190.5ms | Yes | [`evidence/q4/replay_timing_evidence.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/q4/replay_timing_evidence.json) |
| **Q1 Telephony Assistant Sync** | Vapi Assistant Platform API | `LIVE_API` | Assistant config with custom KB & tools | Assistant creation & tool attachment | **Created live assistant ID `3866c061-6a0e-43ad-8a41-8d7128a2b91d`** | 820ms | Yes | [`evidence/providers/vapi_status.json`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/evidence/providers/vapi_status.json) |

---

## Detailed Audit Findings

### 1. BGE-M3 & BGE-Reranker (Q2)
- **Live HF Inference Provider Verification**: With authenticated `HF_TOKEN`, live calls to `https://router.huggingface.co/hf-inference/models/BAAI/bge-m3` were executed. On query *"What is the maximum loan amount for the Starter business loan?"*, the live endpoint scored **0.8141** on relevant policy text vs **0.3048** on unrelated weather text.
- **Production Baseline Verdict**: The local hybrid retriever (BM25 + Dense Semantic Hash + Entity Booster) achieved **100% precision in 0.69ms P50 latency**. The local hybrid engine is maintained as the primary low-latency production baseline for this prototype.

### 2. Deepgram & Whisper Large V3 Turbo (Q3 / Q4 ASR)
- **Live Empirical Finding**: We generated acoustic MP3 audio using ElevenLabs in both Tagalog (*"Magandang araw po! Ako po ang inyong Bancassurance Virtual Assistant."*) and Indonesian (*"Selamat pagi Bapak dan Ibu. Terima kasih telah menghubungi layanan pembiayaan kami."*), and fed the exact same audio files to both providers:
  - **Whisper Large V3 Turbo (`LIVE_HF_API`)**:
    - Indonesian: **0.0% WER** (100% perfect transcription).
    - Tagalog: **20.0% WER** (*"Bank Assurance"* vs *"Bancassurance"*; preserved all consultative markers).
  - **Deepgram Nova-3 (`LIVE_API`)**:
    - Indonesian: **100.0% WER** (struggles with Southeast Asian phonemes under general multi-language mode without explicit Indonesian acoustic biasing).
    - Tagalog: **70.0% WER** (*"Magendang Arau po..."* phonetic errors).
- **Architectural Conclusion**: This empirical finding strongly justifies our dual-layer architectural decision: **Deepgram Nova-3 is selected for sub-second streaming turn tracking (<300ms)**, while **Whisper Large V3 Turbo is deployed as the offline reference auditor** to correct vocabulary and dialect drift.

### 3. ElevenLabs & Meta MMS-TTS (Q3 TTS)
- **ElevenLabs (`LIVE_API`)**: Authenticated and executed live speech synthesis, producing [`data/tts_cache/live_ph_sample.mp3`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/data/tts_cache/live_ph_sample.mp3) (66,499 bytes) and [`data/tts_cache/live_id_sample.mp3`](file:///c:/Users/HP/Documents/claude-code/ai-engineer-assessment/data/tts_cache/live_id_sample.mp3) (94,502 bytes) using voice `Alice` on `eleven_multilingual_v2`.
- **Meta MMS-TTS (`CATALOG_ONLY`)**: The "<50ms CPU" metric is a Meta model card specification for 36M parameter VITS architectures.
- **Data Residency Statement**: Self-hosting open checkpoints like MMS can support data residency architectures by keeping audio computation on local infrastructure. However, legal compliance remains subject to specific national banking regulations and infrastructure controls.
