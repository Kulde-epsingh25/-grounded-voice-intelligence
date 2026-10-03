"""
Q1 Voice Agent — Agent Tools.

Provides execution functions for the voice assistant:
1. search_knowledge: Queries Q2 hybrid retrieval with zero-hallucination confidence gating
2. evaluate_qualification: Deterministic rule evaluation
3. create_lead: Idempotent lead creation
4. escalate_to_human: Human handoff request
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from app.agents.qualification import QualificationManager
from app.agents.rules import evaluate_qualification as run_rules
from app.agents.schemas import (
    QualificationResult,
    QualificationState,
    QualificationStatus,
)
from app.api.kb import ensure_kb_loaded, get_retriever
from app.core.logging import get_logger
from app.retrieval.confidence import ConfidenceGate
from app.services.call_events import get_call_event_service
from app.services.leads import get_lead_service

logger = get_logger(__name__)


def search_knowledge(query: str, filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Execute grounded knowledge retrieval using Q2 hybrid retrieval."""
    ensure_kb_loaded()
    retriever = get_retriever()
    result = retriever.search(query=query, filters=filters)

    if result.grounded:
        return {
            "query": query,
            "grounded": True,
            "confidence": result.confidence,
            "answer": result.answer,
            "citations": [c.model_dump(mode="json") for c in result.citations],
            "fallback_offered": False,
        }

    return {
        "query": query,
        "grounded": False,
        "confidence": result.confidence,
        "answer": ConfidenceGate.DEFAULT_FALLBACK_ANSWER,
        "citations": [],
        "fallback_offered": True,
        "abstain_reason": result.abstain_reason or "insufficient_evidence",
    }


def evaluate_qualification_tool(
    fields: dict[str, Any],
    turn_index: int = 1,
) -> dict[str, Any]:
    """Evaluate application fields against deterministic qualification rules."""
    manager = QualificationManager()
    for k, v in fields.items():
        manager.update_field(name=k, raw_value=v, turn_index=turn_index)

    result: QualificationResult = run_rules(manager.state)
    return {
        "status": result.status.value,
        "recommended_product": result.recommended_product,
        "max_eligible_amount": result.max_eligible_amount,
        "interest_rate": result.interest_rate,
        "term_months": result.term_months,
        "reasons": result.reasons,
        "missing_fields": result.missing_fields,
        "rules_checked": result.rules_checked,
        "is_synthetic": result.is_synthetic,
    }


def create_lead_tool(
    call_id: str,
    fields: dict[str, Any],
    qualification_status: str = "PENDING",
    recommended_product: Optional[str] = None,
    contact_permission: Optional[bool] = None,
    notes: str = "",
) -> dict[str, Any]:
    """Create a persistent lead record for qualified applicant."""
    lead_service = get_lead_service()
    lead = lead_service.create_or_update_lead(
        call_id=call_id,
        qualification_data=fields,
        qualification_status=qualification_status,
        recommended_product=recommended_product,
        contact_permission=contact_permission if contact_permission is not None else False,
        notes=notes,
    )

    get_call_event_service().log_event(
        call_id=call_id,
        event_type="lead_created",
        payload={"lead_id": lead.lead_id, "status": lead.qualification_status},
    )

    return {
        "lead_id": lead.lead_id,
        "call_id": lead.call_id,
        "status": "created",
        "qualification_status": lead.qualification_status,
        "recommended_product": lead.recommended_product,
    }


def escalate_to_human_tool(call_id: str, reason: str) -> dict[str, Any]:
    """Trigger human escalation."""
    escalation_record = {
        "escalation_id": f"esc_{uuid4().hex[:8]}",
        "call_id": call_id,
        "reason": reason,
        "status": "requested",
        "message": (
            "I'll arrange for a lending specialist to follow up with you. "
            "This demo will record the handoff request and prepare your case for callback."
        ),
    }

    get_call_event_service().log_event(
        call_id=call_id,
        event_type="escalation_requested",
        payload=escalation_record,
    )

    return escalation_record
