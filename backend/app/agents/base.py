"""
Q1 Voice Agent — Core Voice Agent Session.

Orchestrates turn-by-turn conversational flow:
- State machine coordination
- Intent detection (knowledge question, objection, qualification, human request)
- Tool invocation (Q2 KB, deterministic rules, lead creation, escalation)
- Event logging and lineage preservation
"""

from __future__ import annotations

import re
from typing import Any, Optional
from uuid import uuid4

from app.agents.qualification import QualificationManager
from app.agents.schemas import (
    AgentAction,
    AgentActionType,
    ConversationState,
    QualificationResult,
    QualificationStatus,
    VoiceAgentTurn,
)
from app.agents.state import ConversationStateMachine
from app.agents.tools import (
    create_lead_tool,
    escalate_to_human_tool,
    evaluate_qualification_tool,
    search_knowledge,
)
from app.core.logging import get_logger
from app.services.call_events import get_call_event_service

logger = get_logger(__name__)


class VoiceAgent:
    """Manages an active conversational voice session."""

    def __init__(self, call_id: Optional[str] = None):
        self.call_id = call_id or f"call_{uuid4().hex[:8]}"
        self.state_machine = ConversationStateMachine()
        self.qualification_manager = QualificationManager()
        self.turn_index = 0
        self.latest_evaluation: Optional[QualificationResult] = None
        self.lead_created = False
        self.escalated = False

        # Log call start
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="call_started",
            payload={"initial_state": self.state_machine.current_state.value},
        )

    def process_turn(self, user_utterance: str) -> VoiceAgentTurn:
        """Process a caller utterance using the intelligence-driven loop."""
        self.turn_index += 1
        clean_utterance = user_utterance.strip()
        state_before = self.state_machine.current_state
        actions_taken: list[AgentAction] = []
        citations_used: list[dict[str, Any]] = []
        grounded = True
        clarification_prompt: Optional[str] = None

        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="user_message",
            payload={"turn": self.turn_index, "text": clean_utterance},
        )

        # 1. INTENT & ENTITY EXTRACTION (The Intelligence Layer)
        # In a full implementation, this calls the LLM.
        # For this immediate fix, we improve the extraction to be less robotic.
        extracted = self._extract_fields(clean_utterance)
        for k, v in extracted.items():
            f_obj = self.qualification_manager.update_field(k, v, turn_index=self.turn_index)
            if f_obj.is_ambiguous:
                clarification_prompt = f_obj.clarification_prompt
            get_call_event_service().log_event(
                call_id=self.call_id,
                event_type="qualification_update",
                payload={"field": k, "value": f_obj.value, "ambiguous": f_obj.is_ambiguous},
            )

        # 2. HIGH PRIORITY DISPATCH
        lower_utt = clean_utterance.lower()
        if any(phrase in lower_utt for phrase in ["human", "representative", "specialist", "agent", "person", "manager", "operator", "speak with someone", "talk to someone"]):
            self.state_machine.transition(ConversationState.ESCALATION, reason="Caller requested human")
            esc_res = escalate_to_human_tool(self.call_id, reason="Caller explicit request")
            actions_taken.append(AgentAction(action_type=AgentActionType.ESCALATE, result=esc_res))
            assistant_response = "I understand. I am transferring you to a lending specialist right now. Please hold on."
            self.escalated = True
            return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # 3. KB GROUNDED RESPONSES (Objections/FAQs)
        if any(phrase in lower_utt for phrase in ["too long", "too high", "why", "how", "rate", "document", "requirement", "can i"]) or "?" in clean_utterance:
            self.state_machine.transition(
                ConversationState.KNOWLEDGE_QUESTION,
                reason="Caller asked a knowledge-base question",
            )
            kb_res = search_knowledge(clean_utterance)
            actions_taken.append(AgentAction(action_type=AgentActionType.SEARCH_KB, parameters={"query": clean_utterance}, result=kb_res))
            if kb_res["grounded"]:
                citations_used = kb_res["citations"]
                assistant_response = kb_res["answer"]
            else:
                grounded = False
                assistant_response = f"{kb_res['answer']} Would you like to speak with an underwriter?"
            if state_before in (ConversationState.QUALIFICATION, ConversationState.OBJECTION):
                self.state_machine.resume_qualification_if_interrupted()
            return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # 4. NATURAL QUALIFICATION FLOW
        self.state_machine.transition(
            ConversationState.QUALIFICATION,
            reason="Caller provided qualification information",
        )
        if clarification_prompt:
            return self._finalize_turn(
                clean_utterance,
                clarification_prompt,
                state_before,
                actions_taken,
                citations_used,
                grounded,
            )

        eval_res = evaluate_qualification_tool(self.qualification_manager.state.to_dict(), turn_index=self.turn_index)
        self.latest_evaluation = QualificationResult.model_validate(eval_res)
        actions_taken.append(AgentAction(action_type=AgentActionType.EVALUATE_QUALIFICATION, result=eval_res))

        status = eval_res["status"]
        if status == QualificationStatus.NEEDS_MORE_INFORMATION.value:
            missing = eval_res["missing_fields"]
            field = missing[0]
            # More natural prompting
            prompts = {
                "business_type": "To get started, could you tell me a bit about the industry or type of business you run?",
                "years_in_business": "And how many years has the business been operating?",
                "monthly_revenue": "I see. What is your average monthly revenue approximately?",
                "requested_amount": "And finally, how much loan funding are you looking to secure?",
            }
            assistant_response = prompts.get(field, "Could you provide more details about your business?")
        elif status == QualificationStatus.ELIGIBLE.value:
            prod = eval_res["recommended_product"]
            assistant_response = f"Great news! You qualify for the {prod} loan. May I create a specialist follow-up for you?"
            lead_res = create_lead_tool(self.call_id, self.qualification_manager.state.to_dict(), "ELIGIBLE", recommended_product=prod, contact_permission=True)
            actions_taken.append(AgentAction(action_type=AgentActionType.CREATE_LEAD, result=lead_res))
            self.lead_created = True
        else:
            assistant_response = f"Thank you. Based on the details, we cannot approve this automatically because {eval_res['reasons'][0]}."

        return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

    def public_state(self) -> dict[str, Any]:
        """Return validated qualification values for the browser interface."""
        state: dict[str, Any] = {}
        for name in (
            "business_type",
            "years_in_business",
            "monthly_revenue",
            "requested_amount",
        ):
            field = getattr(self.qualification_manager.state, name)
            if field is not None and field.validated:
                state[name] = field.value

        evaluation = self.latest_evaluation
        state["eligibility"] = evaluation.status.value if evaluation else "PENDING"
        state["product"] = evaluation.recommended_product if evaluation else None
        return state

    def _finalize_turn(self, utterance, response, state_before, actions, citations, grounded) -> VoiceAgentTurn:
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="assistant_message",
            payload={"turn": self.turn_index, "text": response},
        )
        return VoiceAgentTurn(
            turn_index=self.turn_index,
            user_utterance=utterance,
            assistant_response=response,
            state_before=state_before,
            state_after=self.state_machine.current_state,
            actions_taken=actions,
            grounded=grounded,
            citations_used=citations,
        )

    def _extract_fields(self, text: str) -> dict[str, Any]:
        """Simple deterministic entity extractor for conversation turn."""
        fields: dict[str, Any] = {}
        lower = text.lower()

        # Business type
        for btype in ["retail", "restaurant", "manufacturing", "construction", "technology", "logistics", "trading", "healthcare"]:
            if btype in lower:
                fields["business_type"] = btype

        # Years
        year_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", lower)
        if year_match:
            fields["years_in_business"] = year_match.group(1)

        # Revenue
        rev_match = re.search(
            r"(?:monthly\s+revenue|revenue|earnings?|monthly\s+income|monthly)\s+(?:is|of|around|about|roughly|approximately|\s)*[\$]?([0-9\.]+\s*(?:thousand|million|k|m)?|[a-z]+)",
            lower,
        )
        if rev_match:
            candidate = rev_match.group(1).strip()
            if candidate not in ("of", "is", "around", "a", "about", "revenue"):
                fields["monthly_revenue"] = candidate
        elif any(w in lower for w in ["fifty", "forty", "thirty", "twenty", "sixty", "seventy", "eighty", "ninety"]):
            for w in ["fifty", "forty", "thirty", "twenty", "sixty", "seventy", "eighty", "ninety"]:
                if w in lower:
                    fields["monthly_revenue"] = w
                    break

        # Requested amount / loan amount
        loan_match = re.search(
            r"(?:loan\s*amount|borrow|loan\s*of|request(?:ing)?|need\s*to\s*borrow|need)\s+(?:is|of|around|about|roughly|approximately|to|for|\s)*[\$]?([0-9\.]+\s*(?:thousand|million|k|m)?|[a-z]+)",
            lower,
        )
        if loan_match:
            candidate = loan_match.group(1).strip()
            if candidate not in ("of", "a", "for", "to", "amount", "loan", "borrow"):
                fields["requested_amount"] = candidate

        # Contact permission
        if any(w in lower for w in [
            "permission", "contact me", "proceed", "agree", "consent",
            "yes, you have", "you have my permission"
        ]):
            fields["contact_permission"] = "yes"

        # Loan purpose
        purpose_match = re.search(r"for\s+([a-z\s]+?)(?:\.|$|,)", lower)
        if purpose_match:
            cand = purpose_match.group(1).strip()
            if len(cand) > 3 and cand not in ("a", "the", "my"):
                fields["loan_purpose"] = cand

        return fields

    def _prompt_for_missing_field(self, field_name: str) -> str:
        prompts = {
            "business_type": "Could you tell me what type of business or industry you operate in?",
            "years_in_business": "How many years has your business been operating?",
            "monthly_revenue": "What is your average monthly revenue?",
            "requested_amount": "How much loan funding are you looking to secure?",
        }
        return prompts.get(field_name, "Could you provide more details?")
