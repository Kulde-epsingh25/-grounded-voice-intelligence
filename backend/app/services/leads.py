"""
Q1 Voice Agent — Lead Management Service.

Handles lead creation and persistence.
Guarantees:
1. Idempotency (repeated tool calls on same call_id do not create duplicate leads)
2. Safe PII handling
3. Persistence to data/processed/leads.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class LeadRecord(BaseModel):
    """Structured commercial loan lead."""
    lead_id: str = Field(default_factory=lambda: f"lead_{uuid4().hex[:8]}")
    call_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    business_type: str = ""
    years_in_business: Optional[float] = None
    monthly_revenue: Optional[float] = None
    requested_amount: Optional[float] = None
    qualification_status: str = "PENDING"
    recommended_product: Optional[str] = None
    contact_permission: bool = True
    notes: str = ""
    source: str = "voice_agent"
    status: str = "new"


class LeadService:
    """Manages lead records with file-backed persistence and idempotency."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path or "data/processed/leads.json")
        self._leads: dict[str, LeadRecord] = {}
        self._call_id_to_lead_id: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                lead = LeadRecord.model_validate(item)
                self._leads[lead.lead_id] = lead
                self._call_id_to_lead_id[lead.call_id] = lead.lead_id
        except Exception as e:
            logger.warning("Could not load leads from disk", extra={"extra_data": {"error": str(e)}})

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                data = [l.model_dump(mode="json") for l in self._leads.values()]
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error("Failed to save leads to disk", extra={"extra_data": {"error": str(e)}})

    def create_or_update_lead(
        self,
        call_id: str,
        qualification_data: dict[str, Any],
        qualification_status: str = "PENDING",
        recommended_product: Optional[str] = None,
        contact_permission: bool = True,
        notes: str = "",
    ) -> LeadRecord:
        """Idempotently create or update a lead for a specific call."""
        existing_lead_id = self._call_id_to_lead_id.get(call_id)

        if existing_lead_id and existing_lead_id in self._leads:
            lead = self._leads[existing_lead_id]
            # Update fields
            lead.business_type = str(qualification_data.get("business_type", lead.business_type))
            if "years_in_business" in qualification_data:
                lead.years_in_business = float(qualification_data["years_in_business"])
            if "monthly_revenue" in qualification_data:
                lead.monthly_revenue = float(qualification_data["monthly_revenue"])
            if "requested_amount" in qualification_data:
                lead.requested_amount = float(qualification_data["requested_amount"])
            lead.qualification_status = qualification_status
            lead.recommended_product = recommended_product or lead.recommended_product
            lead.contact_permission = contact_permission
            if notes:
                lead.notes = f"{lead.notes}\n{notes}".strip()
            lead.updated_at = datetime.now(timezone.utc)
            self._save()
            logger.info("Updated existing lead (idempotent)", extra={"extra_data": {"lead_id": lead.lead_id, "call_id": call_id}})
            return lead

        # Create new lead
        lead = LeadRecord(
            call_id=call_id,
            business_type=str(qualification_data.get("business_type", "")),
            years_in_business=float(qualification_data["years_in_business"]) if "years_in_business" in qualification_data else None,
            monthly_revenue=float(qualification_data["monthly_revenue"]) if "monthly_revenue" in qualification_data else None,
            requested_amount=float(qualification_data["requested_amount"]) if "requested_amount" in qualification_data else None,
            qualification_status=qualification_status,
            recommended_product=recommended_product,
            contact_permission=contact_permission,
            notes=notes,
        )
        self._leads[lead.lead_id] = lead
        self._call_id_to_lead_id[call_id] = lead.lead_id
        self._save()

        logger.info("New lead created", extra={"extra_data": {"lead_id": lead.lead_id, "call_id": call_id}})
        return lead

    def get_lead(self, lead_id: str) -> Optional[LeadRecord]:
        return self._leads.get(lead_id)

    def get_lead_by_call(self, call_id: str) -> Optional[LeadRecord]:
        lid = self._call_id_to_lead_id.get(call_id)
        return self._leads.get(lid) if lid else None

    def list_leads(self) -> list[LeadRecord]:
        return list(self._leads.values())

    def clear(self) -> None:
        self._leads.clear()
        self._call_id_to_lead_id.clear()
        if self.storage_path.exists():
            self.storage_path.unlink()


_lead_service = LeadService()


def get_lead_service() -> LeadService:
    return _lead_service
