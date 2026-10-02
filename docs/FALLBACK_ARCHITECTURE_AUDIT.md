# Architecture Audit: Fallback Provider Integration

This document audits the existing provider architecture of the AI Engineer Assessment platform prior to introducing the free/free-tier fallback providers.

---

## 1. Executive Summary

The platform currently relies on four primary cloud providers across key speech, language, and telephony modalities:
- **Voice Platform**: Vapi (telephony, Web SDK, webhook dispatch)
- **Large Language Model (LLM)**: OpenAI (`gpt-4o-mini`, `text-embedding-3-small`)
- **Automatic Speech Recognition (ASR)**: Deepgram (Nova-3 streaming WebSocket)
- **Text-to-Speech (TTS)**: ElevenLabs (`eleven_multilingual_v2`)
- **Retrieval (Q2)**: Hybrid BGE-M3 / BM25 / Qdrant with deterministic local fallback

The objective is to establish an **automatic, resilient fallback routing layer** without removing, modifying, or degrading any existing primary provider paths.

```text
                     APPLICATION / USER REQUEST
                                 │
                     PROVIDER ROUTING LAYER
                                 │
     ┌───────────────────┬───────┴───────────┬───────────────────┐
     │                   │                   │                   │
  Q1 VOICE              LLM                 ASR                 TTS
     │                   │                   │                   │
┌────┴────┐         ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
│  Vapi   │         │ OpenAI  │         │Deepgram │         │ Eleven  │
│ PRIMARY │         │ PRIMARY │         │ PRIMARY │         │ PRIMARY │
└────┬────┘         └────┬────┘         └────┬────┘         └────┬────┘
     │                   │                   │                   │
     ↓ (failure)         ↓ (failure)         ↓ (failure)         ↓ (failure)
Gemini Live           Gemini              Gemini              Gemini TTS
                         ↓ (failure)         ↓ (failure)         ↓ (failure)
                       Groq               HF Whisper            HF MMS
                         ↓ (failure)
                     OpenRouter
```

---

## 2. Component-by-Component Provider Audit

### 2.1 Large Language Model (LLM)

| Aspect | Current Architecture | Fallback Architecture |
| :--- | :--- | :--- |
| **Component** | LLM Generation & Reasoning | LLM Multi-Provider Fallback Chain |
| **Current Primary** | OpenAI (`gpt-4o-mini`) | OpenAI (`gpt-4o-mini`) |
| **Existing Interface** | Configured via `OpenAIConfig`, invoked via SDK/Vapi assistant configs | `LLMProvider` Protocol (`generate`, `generate_stream`) returning `ProviderResult` |
| **Existing Implementation** | `backend/app/core/config.py`, `backend/app/retrieval/embeddings.py`, `backend/app/integrations/vapi/assistant.py` | Central `LLMService` in `backend/app/core/providers/llm.py` |
| **Fallback Insertion Point** | Intercept calls through `execute_with_fallback`: OpenAI → Gemini → Groq → OpenRouter |
| **Existing Tests** | `test_agent_tools.py`, `test_integration_q1_q2.py`, `test_fallback.py` |
| **Potential Breaking Points** | Discrepancies in system prompt handling, function-calling formats, parameter names (`max_tokens` vs `max_output_tokens`). |

### 2.2 Speech-to-Text / ASR

| Aspect | Current Architecture | Fallback Architecture |
| :--- | :--- | :--- |
| **Component** | Real-time & Chunk Speech-to-Text | ASR Multi-Provider Fallback Chain |
| **Current Primary** | Deepgram (`nova-3` / multilingual streaming) | Deepgram (`nova-3`) |
| **Existing Interface** | `StreamingASR` in `backend/app/realtime/asr.py`, `DeepgramStreamingAdapter` in `backend/app/integrations/asr/deepgram.py` | `ASRProvider` Protocol (`transcribe`, `stream_transcribe`) returning `Transcript` |
| **Existing Implementation** | `backend/app/integrations/asr/deepgram.py`, `backend/app/realtime/asr.py` | Deepgram → Gemini Transcribe (`backend/app/integrations/gemini/transcription.py`) → HF Whisper (`backend/app/integrations/huggingface/whisper.py`) |
| **Fallback Insertion Point** | `backend/app/realtime/session.py` and `ASRService` wrapper in `backend/app/realtime/asr.py` |
| **Existing Tests** | `test_replay.py`, `test_realtime_api.py`, `test_realtime_models.py`, `test_hf_integration.py` |
| **Potential Breaking Points** | Audio encoding (PCM 16-bit 16kHz vs MP3/WAV container), chunk latency differences between streaming websockets and batch fallback calls. |

### 2.3 Text-to-Speech (TTS)

| Aspect | Current Architecture | Fallback Architecture |
| :--- | :--- | :--- |
| **Component** | Multilingual Speech Synthesis (PH/ID) | TTS Multi-Provider Fallback Chain |
| **Current Primary** | ElevenLabs (`eleven_multilingual_v2`) | ElevenLabs (`eleven_multilingual_v2`) |
| **Existing Interface** | `TTSClient.synthesize_or_manifest` in `backend/app/integrations/tts/client.py` | `TTSProvider` Protocol (`synthesize`) returning `TTSSynthesisRecord` / audio bytes |
| **Existing Implementation** | `backend/app/integrations/tts/client.py`, `backend/app/integrations/tts/models.py` | ElevenLabs → Gemini TTS (`backend/app/integrations/gemini/tts.py`) → Local HF MMS (`backend/app/integrations/huggingface/tts.py`) |
| **Fallback Insertion Point** | `TTSService` wrapping `TTSClient` with fallback runner |
| **Existing Tests** | `test_hf_integration.py`, `test_localization.py` |
| **Potential Breaking Points** | Voice ID mapping differences between ElevenLabs presets and Gemini/MMS models; output sample rates. |

### 2.4 Voice Platform & Live Session (Q1)

| Aspect | Current Architecture | Fallback Architecture |
| :--- | :--- | :--- |
| **Component** | Voice Orchestration & Telephony | Dual Voice Transport (Vapi + Gemini Live Fallback) |
| **Current Primary** | Vapi Web SDK + Vapi Webhook API | Vapi (Primary) |
| **Existing Interface** | `POST /api/v1/vapi/webhook`, `GET /api/v1/vapi/config` | Gemini Live WebSocket / REST Bridge (`/api/v1/gemini/session`, `/api/v1/gemini/chat`) calling identical Q1 agent tools |
| **Existing Implementation** | `backend/app/api/vapi.py`, `frontend/voice/app.js` | `backend/app/integrations/gemini/live.py`, `backend/app/api/gemini.py`, frontend auto-switch / manual selector |
| **Fallback Insertion Point** | Frontend `startCall()`: attempts Vapi Web SDK; on connection failure or missing key, falls back seamlessly to Gemini Live |
| **Existing Tests** | `test_integration_q1_q2.py`, `test_agent_tools.py`, `test_leads.py` |
| **Potential Breaking Points** | Inadvertently diverging business logic; Gemini Live must strictly use the single source of truth tools (`search_knowledge`, `evaluate_qualification`, `create_lead`, `escalate_to_human`). |

---

## 3. Failure vs Non-Failure Definitions

Fallback activation must strictly adhere to network and provider availability boundaries:

### Conditions That Trigger Fallback:
1. **Network & Connection Failures**: Connection timeouts, DNS resolution failure, connection refused, network unreachable.
2. **Provider Availability Failures**: HTTP 429 (Rate Limit / Quota Exceeded), HTTP 500, 502, 503, 504.
3. **Configuration Gaps**: Missing primary environment variable (`OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `VAPI_API_KEY`).
4. **Forced Simulation Switches**: Development environment overrides (`MOCK_OPENAI_FAILURE=true`, etc.).

### Conditions That Do NOT Trigger Fallback (Surface Normally):
1. **Invalid User Input**: Missing parameters, malformed JSON from caller.
2. **Validation Errors**: Range errors, type mismatches.
3. **Business Rule Decisions**: Loan disqualification, ineligible business criteria.
4. **Grounded Retrieval Abstentions**: Low-confidence queries that correctly trigger safe abstention.
5. **Programming / Schema Bugs**: Internal application bugs.

---

## 4. Telemetry and Health Tracking Plan

The fallback subsystem will maintain:
1. **Circuit Breakers / Health State**: Provider status (`healthy`, `degraded`, `standby`, `unavailable`), tracking success count, failure count, consecutive failures, and last error.
2. **Detailed Request Lineage**: Correlation ID, operation type, primary provider, fallback provider used, latencies, and fallback status.
3. **Provider Status Endpoint**: `GET /api/v1/providers/status` exposing configured/standby statuses with zero leaked secrets.
4. **Truthful Verification Standard**:
   - `CONFIGURED`: Keys exist in environment.
   - `LIVE VERIFIED`: Verified via live remote API call.
   - `MOCK VERIFIED`: Verified via simulated fault-injection test.
   - `LOCAL VERIFIED`: Verified via self-hosted local model / in-memory fixture.
