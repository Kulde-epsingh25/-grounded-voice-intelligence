"""Script to run simulated voice scenarios, generate audit evidence, and populate evidence/q1/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.agents.base import VoiceAgent
from app.agents.schemas import ConversationState
from app.services.call_events import get_call_event_service
from app.services.leads import get_lead_service


from app.agents.rules import evaluate_qualification


def run_scenario(
    scenario_id: str,
    name: str,
    description: str,
    utterances: list[str],
) -> dict:
    """Run an interactive conversation scenario through the VoiceAgent."""
    call_id = f"sim-{scenario_id}"
    agent = VoiceAgent(call_id=call_id)
    history = []

    for turn_idx, text in enumerate(utterances, start=1):
        turn = agent.process_turn(text)
        history.append({
            "turn": turn_idx,
            "caller": text,
            "agent": turn.assistant_response,
            "state_before": turn.state_before.value,
            "state_after": turn.state_after.value,
            "grounded": turn.grounded,
            "citations": turn.citations_used,
            "actions": [
                {
                    "action_type": a.action_type.value,
                    "parameters": a.parameters,
                    "result_summary": a.result.get("status") or a.result.get("result") or ("grounded" if a.result.get("grounded") else "ungrounded")
                }
                for a in turn.actions_taken
            ],
        })

    lead_record = None
    if agent.lead_created:
        leads = get_lead_service().list_leads()
        matched = [l for l in leads if l.call_id == call_id]
        if matched:
            lead_record = matched[0].model_dump(mode="json")

    eval_res = evaluate_qualification(agent.qualification_manager.state)

    return {
        "scenario_id": scenario_id,
        "name": name,
        "description": description,
        "call_id": call_id,
        "call_type": "SIMULATION — NOT LIVE CALL",
        "final_state": agent.state_machine.current_state.value,
        "qualification_state": agent.qualification_manager.state.to_dict(),
        "qualification_status": eval_res.status.value,
        "lead_created": agent.lead_created,
        "lead_record": lead_record,
        "escalated": agent.escalated,
        "transcript": history,
    }


def main():
    q1_dir = Path(__file__).resolve().parent.parent / "evidence" / "q1"
    calls_dir = q1_dir / "calls"
    calls_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        {
            "id": "scenario-01",
            "name": "Cooperative Qualification",
            "desc": "Customer answers qualification questions normally and qualifies for Growth Loan.",
            "turns": [
                "Hello, I run a retail grocery business.",
                "We have been in business for 3 years.",
                "Our monthly revenue is around 1.2 million dollars.",
                "We need to borrow 2 million for inventory expansion.",
                "Yes, you have my permission to proceed and contact me.",
            ],
        },
        {
            "id": "scenario-02",
            "name": "Customer Objection Handled via Q2",
            "desc": "Customer objects that 5 to 7 days processing time is too long. Agent retrieves grounded policy from Q2 and continues.",
            "turns": [
                "I run an online electronics shop.",
                "Why is processing time 5 to 7 business days? That is too long for our suppliers.",
                "We have been operating for 3 years, with 1.5 million monthly revenue.",
            ],
        },
        {
            "id": "scenario-03",
            "name": "Incomplete and Ambiguous Information",
            "desc": "Customer gives vague revenue ('around fifty'). Agent clarifies without guessing denominations.",
            "turns": [
                "Hi, I run a logistics startup.",
                "Our monthly revenue is around fifty.",
            ],
        },
        {
            "id": "scenario-04",
            "name": "Out of Scope Knowledge Question",
            "desc": "Customer asks about an unsupported topic (cryptocurrency lending). Agent safely abstains via Q2 confidence gate, then answers a grounded question.",
            "turns": [
                "Do you offer collateralized Bitcoin and crypto business loans?",
                "What documents are required to apply for a business loan?",
            ],
        },
        {
            "id": "scenario-05",
            "name": "Human Representative Escalation",
            "desc": "Customer requests to speak with a human underwriter. Agent triggers immediate escalation.",
            "turns": [
                "I need to speak with a human specialist to discuss a custom syndicate financing package.",
            ],
        },
    ]

    all_results = []
    qualification_results = []
    fallback_examples = []
    escalation_examples = []

    for idx, sc in enumerate(scenarios, start=1):
        res = run_scenario(
            scenario_id=sc["id"],
            name=sc["name"],
            description=sc["desc"],
            utterances=sc["turns"],
        )
        all_results.append(res)

        # Write call file
        call_filename = f"call-0{idx}.json"
        with open(calls_dir / call_filename, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)

        # Collect qualification results
        qualification_results.append({
            "scenario": sc["name"],
            "call_id": res["call_id"],
            "qualification_status": res["qualification_status"],
            "lead_created": res["lead_created"],
            "state": res["qualification_state"],
        })

        # Collect fallbacks
        for t in res["transcript"]:
            if not t["grounded"] or "clarify" in t["agent"].lower() or "don't have verified" in t["agent"].lower():
                fallback_examples.append({
                    "scenario": sc["name"],
                    "caller_query": t["caller"],
                    "agent_response": t["agent"],
                    "grounded": t["grounded"],
                    "state": t["state_after"],
                })

        # Collect escalations
        if res["escalated"]:
            escalation_examples.append({
                "scenario": sc["name"],
                "call_id": res["call_id"],
                "trigger": res["transcript"][0]["caller"],
                "status": "requested",
                "final_state": res["final_state"],
            })

    # Write test_scenarios.json
    with open(q1_dir / "test_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)

    # Write qualification_results.json
    with open(q1_dir / "qualification_results.json", "w", encoding="utf-8") as f:
        json.dump(qualification_results, f, indent=2)

    # Write fallback_examples.json
    with open(q1_dir / "fallback_examples.json", "w", encoding="utf-8") as f:
        json.dump(fallback_examples, f, indent=2)

    # Write escalation_examples.json
    with open(q1_dir / "escalation_examples.json", "w", encoding="utf-8") as f:
        json.dump(escalation_examples, f, indent=2)

    print("Q1 Evidence successfully generated in evidence/q1/")


if __name__ == "__main__":
    main()
