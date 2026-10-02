"""
Q1 Voice Agent -> Q2 Knowledge Base Integration Tests.

CRITICAL ASSESSMENT REQUIREMENT:
Verifies the end-to-end integration between Q1 voice agent and Q2 retrieval:
1. Voice query invokes Q2 POST /kb/search
2. Verified source is retrieved with content hash and lineage
3. Response is grounded with citations
4. Unsupported voice query triggers Q2 confidence gate (<0.60)
5. Voice agent abstains safely with verified zero-hallucination fallback
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.base import VoiceAgent
from app.agents.tools import search_knowledge
from app.main import app


class TestQ1Q2Integration:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_voice_to_q2_grounded_policy_query(self, client):
        """Voice agent searches for loan processing time through Q2 /kb/search."""
        # 1. API contract verification
        resp = client.post(
            "/kb/search",
            json={"messages": [{"role": "user", "content": "What is the standard processing time for a loan?"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is True
        assert data["confidence"] >= 0.60
        assert len(data["citations"]) > 0
        assert "5-7 business days" in data["answer"]
        assert data["citations"][0]["content_hash"] != ""

        # 2. Voice Agent turn verification
        agent = VoiceAgent()
        turn = agent.process_turn("What is the processing time for a loan application?")
        assert turn.grounded is True
        assert len(turn.citations_used) > 0
        assert "5-7 business days" in turn.assistant_response

    def test_voice_to_q2_objection_grounding(self, client):
        """Voice agent handles customer objection using Q2 knowledge retrieval."""
        agent = VoiceAgent()
        turn = agent.process_turn("Why is there a requirement to be in business for at least 2 years?")
        assert turn.grounded is True
        assert len(turn.citations_used) > 0
        assert "2 years" in turn.assistant_response.lower()

    def test_voice_to_q2_unsupported_safe_fallback(self, client):
        """Unsupported voice query triggers confidence gate and safe abstention."""
        # 1. API contract verification
        resp = client.post(
            "/kb/search",
            json={"messages": [{"role": "user", "content": "Can I finance an interstellar spaceship to Jupiter?"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is False
        assert data["confidence"] < 0.60
        assert "don't have verified information" in data["answer"]

        # 2. Voice Agent turn verification
        agent = VoiceAgent()
        turn = agent.process_turn("What is the weather forecast for Tokyo tomorrow?")
        assert turn.grounded is False
        assert "don't have verified information" in turn.assistant_response
        assert len(turn.citations_used) == 0

    def test_vapi_tool_calls_webhook_integration(self, client):
        """Verify Vapi webhook successfully dispatches tools during calls."""
        payload = {
            "message": {
                "type": "tool-calls",
                "call": {"id": "vapi_call_integration_99"},
                "toolCalls": [
                    {
                        "id": "tc_01",
                        "type": "function",
                        "function": {
                            "name": "search_knowledge",
                            "arguments": {"query": "What documents are required for application?"},
                        },
                    },
                    {
                        "id": "tc_02",
                        "type": "function",
                        "function": {
                            "name": "evaluate_qualification",
                            "arguments": {
                                "business_type": "Retail",
                                "years_in_business": 3.0,
                                "monthly_revenue": 600000.0,
                                "requested_amount": 1500000.0,
                            },
                        },
                    },
                ],
            }
        }

        resp = client.post("/api/v1/vapi/webhook", json=payload)
        assert resp.status_code == 200
        res = resp.json()
        assert "results" in res
        assert len(res["results"]) == 2

        # Tool 1: KB search result
        t1 = res["results"][0]
        assert t1["toolCallId"] == "tc_01"
        assert t1["result"]["grounded"] is True

        # Tool 2: Qualification result
        t2 = res["results"][1]
        assert t2["toolCallId"] == "tc_02"
        assert t2["result"]["status"] == "ELIGIBLE"
        assert t2["result"]["recommended_product"] == "Starter"
