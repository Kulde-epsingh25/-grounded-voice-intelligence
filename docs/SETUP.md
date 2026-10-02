# Setup & Execution Guide

This guide provides step-by-step instructions to set up, run, test, and evaluate the AI Engineer Assessment prototype on **Windows (PowerShell)** and **Linux / macOS (Bash)**.

---

## 1. System Requirements

- **Python**: Version 3.10 to 3.14 (Tested on Python 3.14 on Windows 11).
- **Git**: Installed and available in PATH.
- **Node.js / npm** (Optional): Only required if customizing frontend assets; the frontend is pure vanilla HTML/JS/CSS served directly by FastAPI.

---

## 2. Environment Setup (REQUIRED)

### Windows PowerShell

```powershell
# 1. Clone repository & navigate to directory
cd C:\Users\HP\Documents\claude-code\ai-engineer-assessment

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
```

### Linux / macOS (Bash)

```bash
cd ai-engineer-assessment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Environment Variables (REQUIRED)

Copy `.env.example` to `.env`:

```powershell
# PowerShell
Copy-Item .env.example .env
```

```bash
# Bash
cp .env.example .env
```

### Key Configurations:
- `APP_ENV`: `development`
- `APP_PORT`: `8000`
- `LOG_LEVEL`: `INFO`
- `RETRIEVAL_CONFIDENCE_THRESHOLD`: `0.60`
- Provider keys (`OPENAI_API_KEY`, `VAPI_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`): Optional for local prototype execution. The system features self-contained deterministic fallback runners, mock embedding generators, and simulation engines when live API keys are absent.

---

## 4. Running the Application (REQUIRED)

Start the unified FastAPI server:

```powershell
# From project root
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

### Accessible Interfaces & Endpoints:
- **Service Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Application Home**: [http://localhost:8000/](http://localhost:8000/) (redirects to the voice demo)
- **Q1 Voice Agent Browser UI**: [http://localhost:8000/voice](http://localhost:8000/voice)
- **Q3 Localized Bots UI**: [http://localhost:8000/markets/](http://localhost:8000/markets/)
- **Q4 Live Insights Dashboard**: [http://localhost:8000/insights](http://localhost:8000/insights)
- **Q2 Custom Knowledge Base Search**: `POST http://localhost:8000/kb/search`
- **Q1 Lead Management API**: `GET http://localhost:8000/api/v1/leads`
- **Q4 Realtime WebSocket**: `ws://localhost:8000/ws/realtime/{session_id}`

---

## 5. Running the Complete Test Suite (REQUIRED)

Execute all 177 unit and integration tests:

```powershell
python -m pytest backend/tests/ -v
```

Expected output:
```text
============================= 177 passed =============================
```

---

## 6. Running Evaluation & Demonstration Scripts (REQUIRED)

All demonstration scripts can run standalone without external API keys:

### A. Q2 Retrieval Evaluation
Executes the retrieval benchmark against test queries, measuring ground truth hit rate, reranker entity ranking, and confidence gate abstentions:
```powershell
python scripts/eval_retrieval.py
```
*Outputs: `evidence/q2/retrieval_results.json`*

### B. Q4 False-Positive & Signal Evaluation
Runs the 28-case evaluation benchmark across cross-sell, compliance, frustration, payment difficulty, and neutral controls:
```powershell
python scripts/eval_q4.py
```
*Outputs: `evidence/q4/false_positive_results.json` and `evidence/q4/signal_results.json`*

### C. Q4 Real-Time 1.0x WAV Audio Replay (Primary Q4 Demo)
Streams the standard 16kHz PCM audio file in 500ms chunks at genuine 1.0x real-time speed, measuring wall-clock scheduling drift and live coaching nudges:
```powershell
python scripts/replay_audio.py data/audio/synthetic_call_sample.wav
```
*Outputs: `evidence/q4/replay_results.json` and `evidence/q4/replay_metadata.json`*

### D. Q4 Four Scenario Replay (Mode C Deterministic Unit Suite)
Executes Scenarios A (Cross-Sell), B (Compliance), C (Frustration), and D (Noisy Input Suppression):
```powershell
python scripts/replay_transcript.py
```
*Outputs: `evidence/q4/required_scenarios.json` and `evidence/q4/nudge_results.json`*

### E. Q3 Multilingual Simulation Runner
Simulates six multi-turn conversations across Philippines (Taglish/Bancassurance) and Indonesia (Bahasa/Multifinance):
```powershell
python scripts/simulate_q3.py
```
*Outputs: `evidence/q3/philippines/call-*.json` and `evidence/q3/indonesia/call-*.json`*

### F. Q1 Evidence Generation
Executes the five canonical qualification scenarios:
```powershell
python scripts/generate_q1_evidence.py
```
*Outputs: `evidence/q1/calls/call-*.json` and `evidence/q1/qualification_results.json`*

---

## 7. Optional Production Enhancements (OPTIONAL)

### Live Vapi Telephony Connection
If you have a live Vapi account and telephone number:
1. Export credentials:
   ```powershell
   $env:VAPI_API_KEY="your-private-vapi-key"
   $env:VAPI_PUBLIC_KEY="your-public-vapi-key"
   ```
2. Start development tunnel (e.g. Cloudflare):
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
3. Update assistant webhooks using the generated tunnel URL:
   ```powershell
   python scripts/configure_vapi.py --server-url https://your-tunnel-url.trycloudflare.com
   ```

### Live Deepgram Streaming ASR
To stream real-time audio through Deepgram Nova 3 WebSocket:
```powershell
$env:DEEPGRAM_API_KEY="your-deepgram-api-key"
```

### Production Vector Database (Qdrant)
To launch the production vector storage service:
```powershell
docker run -p 6333:6333 qdrant/qdrant
```
