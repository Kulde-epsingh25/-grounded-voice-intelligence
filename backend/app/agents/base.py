"""
Q1 Voice Agent - Core Voice Agent Session.

Orchestrates turn-by-turn conversational flow:
- State machine coordination
- LLM-driven intent detection and entity extraction (with regex fallback)
- Tool invocation (Q2 KB, deterministic rules, lead creation, escalation)
- Event logging and lineage preservation
"""

from __future__ import annotations

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

        # Conversation history for multi-turn LLM context
        self._history: list[dict[str, str]] = []

        # Log call start
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="call_started",
            payload={"initial_state": self.state_machine.current_state.value},
        )

    def process_turn(self, user_utterance: str) -> VoiceAgentTurn:
        """Process a caller utterance using the LLM-driven intelligence loop."""
        self.turn_index += 1
        clean_utterance = user_utterance.strip()
        state_before = self.state_machine.current_state
        actions_taken: list[AgentAction] = []
        citations_used: list[dict[str, Any]] = []
        grounded = True

        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="user_message",
            payload={"turn": self.turn_index, "text": clean_utterance},
        )

        # 1. INTENT & ENTITY EXTRACTION
        # Uses LLM for semantic understanding when available,
        # falls back to enhanced regex when in a running async loop or on failure.
        from app.agents.llm_extractor import get_extractor
        extractor = get_extractor()
        extraction = extractor.extract_sync(clean_utterance, self._history)

        logger.info(
            "Extraction result",
            extra={"extra_data": {
                "intent": extraction.intent,
                "fields": extraction.fields,
                "source": extraction.source,
                "ambiguous": extraction.ambiguous_fields,
            }},
        )

        # 2. Update qualification state from extracted fields
        for k, v in extraction.fields.items():
            f_obj = self.qualification_manager.update_field(k, v, turn_index=self.turn_index)
            get_call_event_service().log_event(
                call_id=self.call_id,
                event_type="qualification_update",
                payload={"field": k, "value": f_obj.value, "ambiguous": f_obj.is_ambiguous},
            )

        # 3. HIGH PRIORITY: Human escalation
        if extraction.intent == "human_escalation":
            self.state_machine.transition(ConversationState.ESCALATION, reason="Caller requested human")
            esc_res = escalate_to_human_tool(self.call_id, reason="Caller explicit request")
            actions_taken.append(AgentAction(action_type=AgentActionType.ESCALATE, result=esc_res))
            assistant_response = "I understand. I am transferring you to a lending specialist right now. Please hold on."
            self.escalated = True
            return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # 4. AMBIGUITY CLARIFICATION -- must happen before field prompting.
        # If the LLM (or regex) flagged ambiguous fields, ask for clarification NOW.
        if extraction.has_ambiguity() and extraction.clarification_needed:
            assistant_response = extraction.clarification_needed
            if state_before == ConversationState.GREETING:
                self.state_machine.transition(ConversationState.QUALIFICATION, reason="Starting qualification")
            return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # Also surface clarifications from qualification manager's own field validation
        for field_name in ["monthly_revenue", "requested_amount"]:
            field_obj = getattr(self.qualification_manager.state, field_name, None)
            if field_obj and field_obj.is_ambiguous and field_obj.clarification_prompt:
                assistant_response = field_obj.clarification_prompt
                if state_before == ConversationState.GREETING:
                    self.state_machine.transition(ConversationState.QUALIFICATION, reason="Starting qualification")
                return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # 5. KNOWLEDGE QUESTIONS / OBJECTIONS
        is_kb_query = (
            extraction.intent in ("knowledge_question", "objection")
            or any(phrase in clean_utterance.lower() for phrase in [
                "too long", "too high", "what documents",
                "what is the rate", "can i qualify", "requirement", "how much does",
            ])
            or ("?" in clean_utterance and extraction.intent not in ("qualification_info", "acknowledgment", "greeting"))
        )

        if is_kb_query:
            # Transition to KNOWLEDGE_QUESTION state before KB lookup
            self.state_machine.transition(
                ConversationState.KNOWLEDGE_QUESTION,
                reason="Handling knowledge query or objection",
            )
            kb_res = search_knowledge(clean_utterance)
            actions_taken.append(AgentAction(
                action_type=AgentActionType.SEARCH_KB,
                parameters={"query": clean_utterance},
                result=kb_res,
            ))
            if kb_res["grounded"]:
                citations_used = kb_res["citations"]
                assistant_response = kb_res["answer"]
            else:
                grounded = False
                assistant_response = (
                    "I don't have verified information about that in our available records. "
                    "Would you like to speak with a specialist who can help further?"
                )
            # State stays KNOWLEDGE_QUESTION for this turn.
            # On the next qualification-intent turn, transition() will advance naturally.
            return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

        # 6. NATURAL QUALIFICATION FLOW
        if state_before == ConversationState.GREETING:
            self.state_machine.transition(ConversationState.QUALIFICATION, reason="Starting qualification")

        eval_res = evaluate_qualification_tool(
            self.qualification_manager.state.to_dict(), turn_index=self.turn_index
        )
        actions_taken.append(AgentAction(action_type=AgentActionType.EVALUATE_QUALIFICATION, result=eval_res))

        status = eval_res["status"]

        if status == QualificationStatus.NEEDS_MORE_INFORMATION.value:
            missing = eval_res["missing_fields"]
            field = missing[0]
            prompts = {
                "business_type": "To get started, could you tell me a bit about the industry or type of business you run?",
                "years_in_business": "And how many years has the business been operating?",
                "monthly_revenue": "I see. What is your average monthly revenue approximately?",
                "requested_amount": "And approximately how much funding are you looking to secure?",
            }
            assistant_response = prompts.get(field, "Could you provide more details about your business?")

        elif status == QualificationStatus.ELIGIBLE.value:
            prod = eval_res["recommended_product"]
            assistant_response = (
                f"Great news! You qualify for the {prod} loan. "
                f"May I create a specialist follow-up for you?"
            )
            lead_res = create_lead_tool(
                self.call_id,
                self.qualification_manager.state.to_dict(),
                "ELIGIBLE",
                recommended_product=prod,
                contact_permission=True,
            )
            actions_taken.append(AgentAction(action_type=AgentActionType.CREATE_LEAD, result=lead_res))
            self.lead_created = True

        elif status == QualificationStatus.MANUAL_REVIEW.value:
            reasons = eval_res.get("reasons", [])
            reason_text = reasons[0] if reasons else "your profile requires further review"
            prod = eval_res.get("recommended_product")
            if prod:
                assistant_response = (
                    f"Your profile qualifies for our {prod} product, though {reason_text}. "
                    f"A specialist will review and contact you. May I create a follow-up record?"
                )
            else:
                assistant_response = (
                    f"Thank you. {reason_text}. "
                    f"I will flag this for an underwriter review. "
                    f"May I get your permission to have a specialist contact you?"
                )
        else:
            reasons = eval_res.get("reasons", [])
            reason_text = reasons[0] if reasons else "the application does not meet current criteria"
            assistant_response = (
                f"Thank you for sharing those details. Unfortunately, {reason_text}. "
                f"Would you like me to connect you with a specialist to discuss your options?"
            )

        return self._finalize_turn(clean_utterance, assistant_response, state_before, actions_taken, citations_used, grounded)

    def _finalize_turn(self, utterance, response, state_before, actions, citations, grounded) -> VoiceAgentTurn:
        get_call_event_service().log_event(
            call_id=self.call_id,
            event_type="assistant_message",
            payload={"turn": self.turn_index, "text": response},
        )
        # Append to history for multi-turn LLM context
        self._history.append({"user": utterance, "assistant": response})

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

    def _prompt_for_missing_field(self, field_name: str) -> str:
        """Natural prompts for collecting missing qualification fields."""
        prompts = {
            "business_type": "Could you tell me what type of business or industry you operate in?",
            "years_in_business": "How many years has your business been operating?",
            "monthly_revenue": "What is your average monthly revenue?",
            "requested_amount": "How much loan funding are you looking to secure?",
        }
        return prompts.get(field_name, "Could you provide more details?")
