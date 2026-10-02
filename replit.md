# Replit Run Guide

## Start the app

The `Start application` workflow runs the FastAPI server on port `5000`, which is the Replit web preview port:

```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 5000
```

The project root redirects to `/voice`. The other main pages are `/markets/` (localized PH/ID demos), `/insights`, `/docs` (API documentation), and `/health`.

Dependencies are installed from `requirements.txt` using Replit's Python package manager. No Docker container or virtual environment is needed. Use the Run button to start the existing workflow.

The voice page defaults to **Direct Voice**, which uses the local qualification API. Quick test scenarios and typed messages do not need provider keys. Browser speech features depend on browser support and microphone permission.

## Run checks

```bash
python -m pytest backend/tests -q
```

## Provider configuration

The deterministic qualification flow, local knowledge base, browser text/voice demo, localized simulations, and real-time WAV replay run without provider credentials.

For browser calls, create an assistant in Vapi and add `VAPI_PUBLIC_KEY` and `VAPI_ASSISTANT_ID` to Replit Secrets. The private `VAPI_API_KEY` is optional unless server-side Vapi assistant management is added. After publishing, set `PUBLIC_BASE_URL` to the published URL and configure the Vapi webhook at `/api/v1/vapi/webhook` with an `X-Vapi-Secret` header matching `VAPI_WEBHOOK_SECRET`.

The published server runs with `APP_ENV=production`. In that mode, the unauthenticated lead-inspection/management API and knowledge-base indexing endpoint are disabled, and Vapi webhooks require the configured secret. Deepgram audio streaming and provider-backed localized TTS are not yet wired end to end; adding those keys alone will not enable them.

## Setup verification

The 179 backend tests pass, and `/health`, `/voice/`, `/markets/`, `/insights/`, and `/docs` respond successfully. The local demos use the prototype knowledge store; a separate Qdrant server is not required for these demos (some retrieval tests warn that no Qdrant server is available). Live provider calls were not verified. The imported Vapi SDK CDN URL currently fails to load; repair that integration before relying on the Vapi mode.