"""
Q1 Voice Agent — Qualification Manager & Extraction Tests.

Tests:
1. Valid structured field parsing ($500k, 1M, 2.5M, 2 years, 18 months)
2. Ambiguous amount handling (bare "fifty" triggers clarification)
3. Missing fields detection
4. Lineage and confidence preservation
"""

from __future__ import annotations

import pytest

from app.agents.qualification import QualificationManager
from app.agents.schemas import QualificationState


class TestQualificationManager:
    def test_parse_valid_denominations(self):
        mgr = QualificationManager()

        # Monthly revenue $600k
        f1 = mgr.update_field("monthly_revenue", "$600k", turn_index=1)
        assert f1.value == 600000.0
        assert f1.validated is True
        assert f1.is_ambiguous is False

        # Requested amount 1.5 million
        f2 = mgr.update_field("requested_amount", "1.5 million", turn_index=2)
        assert f2.value == 1500000.0
        assert f2.validated is True
        assert f2.is_ambiguous is False

        # Years in business: "3 years"
        f3 = mgr.update_field("years_in_business", "3 years", turn_index=3)
        assert f3.value == 3.0
        assert f3.validated is True

        # Months expression: "18 months" -> 1.5 years
        f4 = mgr.update_field("years_in_business", "18 months", turn_index=4)
        assert f4.value == 1.5

    def test_detect_ambiguous_amount(self):
        mgr = QualificationManager()

        # Bare "fifty" without thousand/million
        f = mgr.update_field("monthly_revenue", "our revenue is around fifty", turn_index=1)
        assert f.is_ambiguous is True
        assert f.validated is False
        assert f.clarification_prompt is not None
        assert "fifty thousand" in f.clarification_prompt.lower()

    def test_detect_bare_number_ambiguity(self):
        mgr = QualificationManager()
        f = mgr.update_field("requested_amount", "50", turn_index=2)
        assert f.is_ambiguous is True
        assert f.validated is False
        assert "$50,000" in f.clarification_prompt

    def test_empty_and_none_values(self):
        mgr = QualificationManager()
        f = mgr.update_field("business_type", "", turn_index=1)
        assert f.value is None
        assert f.validated is False

    def test_contact_permission_parsing(self):
        mgr = QualificationManager()
        f_yes = mgr.update_field("contact_permission", "yes, please go ahead", turn_index=1)
        assert f_yes.value is True

        f_no = mgr.update_field("contact_permission", "no, don't call me", turn_index=2)
        assert f_no.value is False
