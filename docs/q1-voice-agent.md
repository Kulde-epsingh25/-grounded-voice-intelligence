# Q1: Knowledge-Grounded Voice Agent

## 1. System Architecture

The Q1 voice agent provides commercial business-loan qualification through an intelligent, voice-first browser interface backed by deterministic qualification rules and source-grounded knowledge from Q2.

### Architectural Boundary
A core architectural principle governs the entire design:
- **The LLM is NOT the source of business truth.**
- **Business Truth** originates exclusively from the **Q2 Knowledge Base** (for product features, document requirements, rates, processing times, and FAQs) and the **Deterministic Rules Engine** (for eligibility decisions).
- The **LLM** manages conversation flow, intent recognition, structured field extraction, and grounding verification. It is strictly prohibited from inventing qualification criteria or answering ungrounded policy questions.

```
Caller (Browser)
   │
   ▼
Vapi Voice Platform (Web SDK / Custom Assistant)
   │
   ├── POST /kb/search ────────► Q2 Knowledge Base (Chunk 2)
   │                                 │
   │                                 ▼
   │                             Grounded Evidence + Citations
   │
   └── POST /api/v1/vapi/webhook (Tool Calls)
         │
         ├── evaluate_qualification ──► Deterministic Rules Engine (rules.py)
         │                                  │
         │                                  ▼
         │                              ELIGIBLE / INELIGIBLE / NEEDS_MORE_INFO / MANUAL_REVIEW
         │
         ├── create_lead ─────────────► Lead Action Service (leads.py)
         │
         └── escalate_to_human ───────► Escalation Handler (tools.py)
```

---

## 2. Vapi Voice Platform Integration

### Client Architecture
- **Browser Frontend**: Vanilla HTML/JavaScript/CSS located at `frontend/voice/`.
- **SDK**: Uses `@vapi-ai/web` browser SDK for WebRTC bidirectional audio streaming.
- **Security Boundary**: Only public Vapi keys (`VAPI_PUBLIC_KEY`) and assistant IDs (`VAPI_ASSISTANT_ID`) are sent to the client browser. The private `VAPI_API_KEY` is strictly confined to server-side scripts and never exposed to the frontend or version control.
- **Dry-Run Mode**: `scripts/configure_vapi.py` supports schema validation and configuration artifact generation (`config/vapi_assistant.json`) without requiring live API keys. When live keys are present, it performs atomic updates to Vapi assistants and custom KB endpoints.

### Development Tunnel
For remote Vapi instances to communicate with local development servers, a webhook tunnel is supported:
- **Cloudflare Quick Tunnel**: `cloudflared tunnel --url http://localhost:8000`
- Configurable via `VAPI_SERVER_URL` in `.env` without hardcoded domains.

---

## 3. Q2 Knowledge Base Integration

The voice assistant communicates directly with Q2 using the standard Vapi Custom Knowledge Base contract:
- **Primary Endpoint**: `POST /kb/search` (also mirrored at `POST /api/v1/kb/search`).
- **Pipeline Execution**:
  1. Voice question received from caller.
  2. Query preprocessed and matched against dense (embeddings) and sparse (BM25) vector indices.
  3. Reciprocal Rank Fusion combines candidate results.
  4. Reranker boosts entity and numeric matches.
  5. Confidence Gate evaluates evidence score against `threshold = 0.60`.
  6. Grounded response formatted with verifiable citations (`[Source: filename | Section: heading | Version: v1.0 | Hash: ... ]`).
  7. If confidence is below threshold, the gate safely abstains.

---

## 4. Conversation State Machine

To prevent unbounded LLM drift and ensure reproducible behavior, the conversation is governed by an explicit finite state machine (`backend/app/agents/state.py`):

| State | Description | Transitions Permitted |
|---|---|---|
| `GREETING` | Initial welcome and identity disclosure | `UNDERSTAND_INTENT`, `QUALIFICATION`, `KNOWLEDGE_QUESTION` |
| `UNDERSTAND_INTENT` | Identify customer goal (loan inquiry, policy question) | `QUALIFICATION`, `KNOWLEDGE_QUESTION`, `OBJECTION` |
| `QUALIFICATION` | Structured data collection turn-by-turn | `QUALIFICATION`, `KNOWLEDGE_QUESTION`, `OBJECTION`, `REVIEW`, `ESCALATION` |
| `KNOWLEDGE_QUESTION` | Temporary branch for answering product/policy questions | Return to `QUALIFICATION`, or move to `ESCALATION` |
| `OBJECTION` | Address caller hesitation with Q2 evidence | Return to `QUALIFICATION`, or move to `ESCALATION`, `END` |
| `REVIEW` | Present eligibility evaluation to applicant | `LEAD_CONFIRMATION`, `ESCALATION`, `END` |
| `LEAD_CONFIRMATION`| Applicant confirms contact permission; lead created | `END` |
| `ESCALATION` | Human representative transfer initiated | `END` |
| `END` | Call completed and audit logged | Terminal |

---

## 5. Structured Qualification State

The application profile is tracked in a strongly typed model (`QualificationState` in `backend/app/agents/schemas.py`). Each collected attribute is wrapped in a `QualificationField`:

```python
class QualificationField(BaseModel):
    name: str
    value: Any
    confidence: float = 1.0
    source_turn: int = 1
    validated: bool = False
    raw_input: str = ""
    is_ambiguous: bool = False
    clarification_prompt: Optional[str] = None
```

### Tracked Fields:
1. `business_type`: Industry classification (e.g., retail, manufacturing, tech).
2. `years_in_business`: Operating history normalized to decimal years.
3. `monthly_revenue`: Average monthly gross revenue in dollars.
4. `requested_amount`: Desired loan funding in dollars.
5. `loan_purpose`: Intent for capital use (e.g., inventory expansion).
6. `existing_loans`: Existing debt obligations.
7. `documents_available`: Confirmation of required documentation.
8. `contact_permission`: Consent for specialist outreach.

---

## 6. Server-Side Extraction & Validation

User utterances are parsed using strict server-side validation (`QualificationManager` in `backend/app/agents/qualification.py`):

- **Denomination Normalization**: Handles `$50k`, `500 thousand`, `1.5M`, `2 million`, `18 months` (converted to 1.5 years).
- **Ambiguity Detection**: Bare words without denominations (e.g., "Our revenue is around fifty") are flagged as ambiguous (`is_ambiguous=True`). The agent prompts: *"Could you clarify if you mean fifty thousand, fifty million, or another amount?"* instead of making assumptions.
- **Impossible & Negative Values**: Rejects negative revenue, negative loan requests, or negative operating years.

---

## 7. Deterministic Rules Engine

Qualification decisions are computed by `evaluate_qualification(state)` in `backend/app/agents/rules.py` without LLM intervention:

### Rules Hierarchy:
1. **Mandatory Field Check**: Verifies presence of all required fields (`business_type`, `years_in_business`, `monthly_revenue`, `requested_amount`). Missing fields return `NEEDS_MORE_INFORMATION` with targeted prompts.
2. **Absolute Eligibility Thresholds**:
   - Minimum 2 years operating history.
   - Minimum $500,000 monthly revenue.
   - Failure returns `INELIGIBLE` with plain-language reasons.
3. **Product Tier Matching**:
   - **Starter**: Revenue >= $500,000, Years >= 2, Max Loan $2,000,000 (12.5% APR)
   - **Growth**: Revenue >= $1,000,000, Years >= 2, Max Loan $5,000,000 (10.0% APR)
   - **Premium**: Revenue >= $2,500,000, Years >= 3, Max Loan $15,000,000 (8.5% APR)
   - **Enterprise**: Revenue >= $5,000,000, Years >= 5, Max Loan $50,000,000 (7.0% APR)
4. **Manual Review Triggers**:
   - Requested amount exceeds tier maximum -> `MANUAL_REVIEW`.
   - Missing business registration or critical document discrepancy -> `MANUAL_REVIEW`.

> [!NOTE]
> Synthetic demo rules are configured in `data/eval/demo_business_rules.json` and clearly labeled:
> `SYNTHETIC DEMO RULES — NOT ASSESSMENT BUSINESS RULES`.

---

## 8. Voice Agent Tools

Four voice-agent-facing tools are registered in `backend/app/agents/tools.py` and exposed via Vapi function calls:

1. `search_knowledge(query)`: Queries Q2 hybrid retrieval for grounded answers and citations.
2. `evaluate_qualification_tool(fields)`: Evaluates collected applicant data against deterministic rules.
3. `create_lead_tool(call_id, fields, ...)`: Idempotently creates CRM lead records for qualified callers.
4. `escalate_to_human_tool(call_id, reason)`: Records human handoff request and initiates escalation protocol.

---

## 9. Objection Handling

Customer hesitations are grounded in verified Q2 documents rather than hardcoded prompts:
- **Processing Time Objection**: *"Why is processing time 5 to 7 days? That is too long."* -> Queries Q2, cites `sample_faq.html`, explains standard 5-7 business day underwriting timelines, and suggests expedited document submission.
- **Interest Rate Objection**: Retrieves product tier rate schedules and explains revenue tier discounts.
- **Documentation Objection**: Retrieves specific required documents from the KB table.

---

## 10. Fallback & Safe Abstention

When questions fall outside verified knowledge base coverage:
- **Out of Scope Question**: e.g., *"Do you offer collateralized Bitcoin loans?"*
- **Action**: Q2 confidence gate yields confidence < 0.60 -> Returns standard fallback:
  > *"I don't have verified information about that in the available knowledge base. Would you like me to connect you with a representative who can look into this?"*
- No internal stack traces, system errors, or ungrounded opinions are presented to the caller.

---

## 11. Human Escalation Protocol

Escalation is triggered under five deterministic conditions:
1. Caller explicitly requests a human representative (*"I want to speak with someone"*).
2. Qualification conflict or complex edge case requiring underwriter discretion (`MANUAL_REVIEW`).
3. Core knowledge inquiry fails retrieval confidence.
4. Caller expresses dissatisfaction or sensitive complaint.
5. Out-of-scope commercial financing request (e.g. syndication, mezzanine debt).

The system creates an audit record (`status: requested`) and transitions to `ConversationState.ESCALATION`.

---

## 12. Persistent Lead Action

- **Service**: `backend/app/services/leads.py`
- **Storage**: JSON/SQLite-compatible persistent file store at `data/leads.json`.
- **Idempotency**: Calls with identical `call_id` update the existing lead rather than creating duplicates.
- **PII Sanitation**: Unnecessary personal identifiers are excluded; names and phones are sanitized.

---

## 13. Call Event Logging

- **Service**: `backend/app/services/call_events.py`
- Structured events logged: `call_started`, `user_message`, `assistant_message`, `kb_search`, `kb_result`, `qualification_update`, `qualification_evaluation`, `lead_created`, `escalation_requested`, `call_ended`, `error`.
- **PII Scrubbing**: Automatic regex scrubbing masks customer emails and phone numbers before serialization.

---

## 14. Testing & Verification

Automated test suite (`100 passed` across project):
- `backend/tests/test_qualification.py` (5 tests): Parsing denominations, bare ambiguity, empty values, consent.
- `backend/tests/test_rules.py` (7 tests): Eligible tiers, ineligibility, missing fields, manual review, impossible numbers.
- `backend/tests/test_agent_tools.py` (4 tests): Knowledge retrieval, rules tool, lead creation, escalation.
- `backend/tests/test_call_events.py` (5 tests): Event sequencing, filtering, PII masking.
- `backend/tests/test_leads.py` (2 tests): Persistence and idempotency.
- `backend/tests/test_fallback.py` (4 tests): Abstention, ambiguity clarification, human request, state machine transitions.
- `backend/tests/test_integration_q1_q2.py` (4 tests): Grounded policy retrieval, objection handling, out-of-scope abstention, Vapi tool webhook dispatch.

---

## 15. Known Limitations & Caveats

1. **Retrieval Store**: Local in-memory/JSON store with dense cosine and sparse BM25 fusion is used for the prototype; production deployment will connect to Qdrant cluster.
2. **Evaluation Metrics**: 100% retrieval accuracy and sub-millisecond latencies are measured on the current local synthetic dataset, not at enterprise vector scale.
3. **Telephony**: Browser voice calling via Vapi Web SDK is the primary interface; telephony PSTN inbound/outbound numbers are mocked for prototype verification.
4. **Call Evidence**: All test call logs in `evidence/q1/calls/` are generated via local multi-turn simulation and explicitly labeled: `SIMULATION — NOT LIVE CALL`.
