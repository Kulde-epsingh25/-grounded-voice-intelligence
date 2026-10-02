"""
Q1 Voice Agent — Data Schemas.

Defines schemas for:
- Strongly typed qualification fields with confidence and turn lineage
- Qualification application state
- Deterministic qualification evaluation results
- Conversation state machine states
- Voice agent actions and turns
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Conversation state machine states."""
    GREETING = "GREETING"
    UNDERSTAND_INTENT = "UNDERSTAND_INTENT"
    QUALIFICATION = "QUALIFICATION"
    KNOWLEDGE_QUESTION = "KNOWLEDGE_QUESTION"
    OBJECTION = "OBJECTION"
    REVIEW = "REVIEW"
    LEAD_CONFIRMATION = "LEAD_CONFIRMATION"
    ESCALATION = "ESCALATION"
    END = "END"


class QualificationStatus(str, Enum):
    """Deterministic qualification outcomes."""
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class QualificationField(BaseModel):
    """A single qualification data point with lineage and validation status."""
    name: str
    value: Any
    confidence: float = 1.0
    source_turn: int = 1
    validated: bool = False
    raw_input: str = ""
    is_ambiguous: bool = False
    clarification_prompt: Optional[str] = None


class QualificationState(BaseModel):
    """Strongly typed qualification profile collected during the call."""
    business_type: Optional[QualificationField] = None
    years_in_business: Optional[QualificationField] = None
    monthly_revenue: Optional[QualificationField] = None
    requested_amount: Optional[QualificationField] = None
    loan_purpose: Optional[QualificationField] = None
    existing_loans: Optional[QualificationField] = None
    documents_available: Optional[QualificationField] = None
    contact_permission: Optional[QualificationField] = None

    def get_field_value(self, name: str) -> Any:
        field: Optional[QualificationField] = getattr(self, name, None)
        return field.value if field is not None else None

    def is_field_validated(self, name: str) -> bool:
        field: Optional[QualificationField] = getattr(self, name, None)
        return bool(field and field.validated and not field.is_ambiguous)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to a plain dictionary of field values."""
        res = {}
        for name in [
            "business_type", "years_in_business", "monthly_revenue",
            "requested_amount", "loan_purpose", "existing_loans",
            "documents_available", "contact_permission",
        ]:
            val = self.get_field_value(name)
            if val is not None:
                res[name] = val
        return res


class QualificationResult(BaseModel):
    """Result of deterministic qualification rules evaluation."""
    status: QualificationStatus
    recommended_product: Optional[str] = None
    max_eligible_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    term_months: Optional[int] = None
    rules_checked: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    is_synthetic: bool = True
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentActionType(str, Enum):
    SPEAK = "SPEAK"
    SEARCH_KB = "SEARCH_KB"
    EVALUATE_QUALIFICATION = "EVALUATE_QUALIFICATION"
    CREATE_LEAD = "CREATE_LEAD"
    ESCALATE = "ESCALATE"
    END_CALL = "END_CALL"


class AgentAction(BaseModel):
    """Action taken by the voice agent."""
    action_type: AgentActionType
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VoiceAgentTurn(BaseModel):
    """A single turn in the conversation."""
    turn_index: int
    user_utterance: str
    assistant_response: str
    state_before: ConversationState
    state_after: ConversationState
    actions_taken: list[AgentAction] = Field(default_factory=list)
    grounded: bool = True
    citations_used: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
