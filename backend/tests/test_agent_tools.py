"""
Q1 Voice Agent — Agent Tools Tests.

Tests:
1. search_knowledge returns grounded answer and citations for supported query
2. search_knowledge safely abstains on out-of-scope query
3. evaluate_qualification_tool executes deterministic rules
4. create_lead_tool creates lead record
5. escalate_to_human_tool returns escalation record
"""

from __future__ import annotations

import pytest

from app.agents.tools import (
    create_lead_tool,
    escalate_to_human_tool,
    evaluate_qualification_tool,
    search_knowledge,
)
from app.services.leads import get_lead_service


class TestAgentTools:
    def test_search_knowledge_grounded(self):
        res = search_knowledge("What is the processing time for loan applications?")
        assert res["grounded"] is True
        assert res["confidence"] >= 0.60
        assert len(res["citations"]) > 0
        assert "5-7 business days" in res["answer"]
        assert res["fallback_offered"] is False

    def test_search_knowledge_abstains_on_unsupported(self):
        res = search_knowledge("What is the weather forecast for Tokyo tomorrow?")
        assert res["grounded"] is False
        assert res["confidence"] < 0.60
        assert len(res["citations"]) == 0
        assert "don't have verified information" in res["answer"]
        assert res["fallback_offered"] is True
        assert res["abstain_reason"] is not None

    def test_evaluate_qualification_tool(self):
        fields = {
            "business_type": "Manufacturing",
            "years_in_business": 4.0,
            "monthly_revenue": 1200000.0,
            "requested_amount": 3000000.0,
        }
        res = evaluate_qualification_tool(fields)
        assert res["status"] == "ELIGIBLE"
        assert res["recommended_product"] == "Growth"
        assert res["interest_rate"] == 10.0

    def test_create_lead_tool(self):
        get_lead_service().clear()
        res = create_lead_tool(
            call_id="call_test_01",
            fields={"business_type": "Retail", "monthly_revenue": 600000.0},
            qualification_status="ELIGIBLE",
            recommended_product="Starter",
        )
        assert res["status"] == "created"
        assert res["lead_id"].startswith("lead_")
        assert res["call_id"] == "call_test_01"

    def test_escalate_to_human_tool(self):
        res = escalate_to_human_tool(call_id="call_test_02", reason="Customer asked for manager")
        assert res["status"] == "requested"
        assert res["call_id"] == "call_test_02"
        assert "specialist" in res["message"].lower()
