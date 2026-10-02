# Changelog

## 2026-10-03 — Replit setup and Q1 browser demo

- Installed the Python packages declared by the existing root requirements file in the Replit environment and configured the `Start application` preview workflow on port 5000.
- Added a Replit run guide with the port-5000 command, preview pages, test command, and optional provider-key notes.
- Added a root redirect to the voice demo, a stateful `/api/v1/agent/turn` endpoint, and a local browser fallback so Q1 remains a clearly labeled working demo without provider credentials.
- Added end-call cleanup for browser agent sessions and updated the Gemini fallback UI to display validated qualification fields and eligibility.
- Fixed Q1 knowledge-question state transitions and made ambiguous financial amounts return their clarification prompt rather than asking for an unrelated missing field.
- Added a localized market API and `/markets/` UI for Philippines Bancassurance and Indonesia Multifinance, including stateful turns, language/register/code-switch reporting, optional browser microphone input, and optional installed-voice speech output.
- Isolated all test lead writes in temporary storage and Q4 evaluation output in a temporary directory so the suite does not overwrite project data or committed evidence.
- Corrected the dependency install path, test-count references, and retrieval-threshold example in the setup documentation.
- Refreshed the test-result scorecard and JSON/text summaries to the verified suite total of 177 passing tests.
- Disabled unauthenticated lead inspection/mutation and knowledge-base indexing in production; production Vapi webhooks now require their configured secret.
- Prepared VM publishing to run the FastAPI/WebSocket app on port 5000 with `APP_ENV=production`, enabling those production safeguards by default.
- Corrected Vapi readiness to depend on the Web SDK public key and existing assistant ID rather than an unused private management key; exposed sanitized management/webhook readiness and documented the actual setup requirements.