"""
ACOE -- Pluggable Integration Adapters
Abstract interface layer for SaaS, Cloud, and Procurement integrations.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("acoe.adapters")


# ── Base Interface ───────────────────────────────────────────────────────────

class BaseAdapter(ABC):
    """Abstract adapter interface. All external integrations implement this."""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.name = self.__class__.__name__

    @abstractmethod
    def cancel(self, entity_id: str, **kwargs) -> dict:
        """Cancel a subscription/service."""

    @abstractmethod
    def downgrade(self, entity_id: str, target_tier: str, **kwargs) -> dict:
        """Downgrade a plan to a lower tier."""

    @abstractmethod
    def get_status(self, entity_id: str) -> dict:
        """Get current status of an entity."""

    @abstractmethod
    def modify(self, entity_id: str, changes: dict) -> dict:
        """Modify an entity's configuration."""


# ── SaaS Adapter ─────────────────────────────────────────────────────────────

class SaaSAdapter(BaseAdapter):
    """Adapter for SaaS subscription management (Slack, Salesforce, etc.)."""

    def cancel(self, entity_id: str, **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"SaaS subscription {entity_id} cancellation initiated",
                "effective_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "refund_eligible": True,
                "provider": "mock_saas",
            }
        # Real API call would go here
        raise NotImplementedError("Real SaaS API not configured")

    def downgrade(self, entity_id: str, target_tier: str = "basic", **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"SaaS {entity_id} downgraded to {target_tier}",
                "new_tier": target_tier,
                "effective_date": datetime.utcnow().isoformat(),
                "monthly_savings_inr": kwargs.get("estimated_monthly_savings", 0),
            }
        raise NotImplementedError("Real SaaS API not configured")

    def get_status(self, entity_id: str) -> dict:
        if self.mock_mode:
            return {"entity_id": entity_id, "status": "active", "type": "saas"}
        raise NotImplementedError("Real SaaS API not configured")

    def modify(self, entity_id: str, changes: dict) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"SaaS {entity_id} modified",
                "changes_applied": changes,
            }
        raise NotImplementedError("Real SaaS API not configured")


# ── Cloud Adapter ────────────────────────────────────────────────────────────

class CloudAdapter(BaseAdapter):
    """Adapter for cloud resource management (AWS, Azure, GCP)."""

    def cancel(self, entity_id: str, **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Cloud resource {entity_id} decommissioned",
                "decommission_date": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            }
        raise NotImplementedError("Real Cloud API not configured")

    def downgrade(self, entity_id: str, target_tier: str = "reduced", **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Cloud resource {entity_id} right-sized to {target_tier}",
                "new_capacity": target_tier,
                "effective_date": datetime.utcnow().isoformat(),
            }
        raise NotImplementedError("Real Cloud API not configured")

    def get_status(self, entity_id: str) -> dict:
        if self.mock_mode:
            return {"entity_id": entity_id, "status": "running", "type": "cloud"}
        raise NotImplementedError("Real Cloud API not configured")

    def modify(self, entity_id: str, changes: dict) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Cloud resource {entity_id} reconfigured",
                "changes": changes,
            }
        raise NotImplementedError("Real Cloud API not configured")

    def reallocate(self, entity_id: str, target_capacity: float) -> dict:
        """Cloud-specific: reallocate compute resources."""
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Resource {entity_id} reallocated to {target_capacity} units",
                "new_capacity": target_capacity,
                "effective_date": datetime.utcnow().isoformat(),
            }
        raise NotImplementedError("Real Cloud API not configured")


# ── Procurement Adapter ──────────────────────────────────────────────────────

class ProcurementAdapter(BaseAdapter):
    """Adapter for procurement / vendor management."""

    def cancel(self, entity_id: str, **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Contract {entity_id} flagged for non-renewal",
                "effective_date": kwargs.get("contract_end", datetime.utcnow().isoformat()),
            }
        raise NotImplementedError("Real Procurement API not configured")

    def downgrade(self, entity_id: str, target_tier: str = "renegotiated", **kwargs) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Contract {entity_id} renegotiation initiated",
                "proposal_id": f"NEG-{uuid.uuid4().hex[:6].upper()}",
                "target_reduction_pct": 15,
            }
        raise NotImplementedError("Real Procurement API not configured")

    def get_status(self, entity_id: str) -> dict:
        if self.mock_mode:
            return {"entity_id": entity_id, "status": "active", "type": "procurement"}
        raise NotImplementedError("Real Procurement API not configured")

    def modify(self, entity_id: str, changes: dict) -> dict:
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Contract {entity_id} modified",
                "changes": changes,
            }
        raise NotImplementedError("Real Procurement API not configured")

    def consolidate(self, primary_id: str, secondary_ids: list[str]) -> dict:
        """Procurement-specific: consolidate multiple vendors."""
        if self.mock_mode:
            return {
                "status": "success",
                "message": f"Consolidation plan: merge {secondary_ids} into {primary_id}",
                "consolidation_id": f"CON-{uuid.uuid4().hex[:6].upper()}",
                "estimated_completion": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            }
        raise NotImplementedError("Real Procurement API not configured")


# ── Escalation Adapter ───────────────────────────────────────────────────────

class EscalationAdapter(BaseAdapter):
    """Adapter for SLA escalation workflows."""

    def cancel(self, entity_id: str, **kwargs) -> dict:
        return {"status": "success", "message": f"Escalation {entity_id} cancelled"}

    def downgrade(self, entity_id: str, target_tier: str = "", **kwargs) -> dict:
        return {"status": "n/a", "message": "Downgrade not applicable to escalations"}

    def get_status(self, entity_id: str) -> dict:
        if self.mock_mode:
            return {"entity_id": entity_id, "status": "open", "type": "escalation"}
        raise NotImplementedError("Real Escalation API not configured")

    def modify(self, entity_id: str, changes: dict) -> dict:
        return {"status": "success", "message": f"Escalation {entity_id} updated"}

    def escalate(self, entity_id: str, priority: str = "critical") -> dict:
        """Create SLA escalation ticket."""
        if self.mock_mode:
            return {
                "status": "success",
                "ticket_id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
                "priority": priority,
                "assigned_to": "vendor_account_manager",
                "message": f"SLA escalation triggered for {entity_id}",
            }
        raise NotImplementedError("Real Escalation API not configured")


# ── Adapter Registry ─────────────────────────────────────────────────────────

class AdapterRegistry:
    """Registry for managing and swapping adapters at runtime."""

    def __init__(self, mock_mode: bool = True):
        self._adapters: dict[str, BaseAdapter] = {
            "saas": SaaSAdapter(mock_mode),
            "cloud": CloudAdapter(mock_mode),
            "procurement": ProcurementAdapter(mock_mode),
            "escalation": EscalationAdapter(mock_mode),
        }

    def get(self, adapter_type: str) -> BaseAdapter:
        adapter = self._adapters.get(adapter_type)
        if not adapter:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        return adapter

    def register(self, name: str, adapter: BaseAdapter):
        """Register or replace an adapter."""
        self._adapters[name] = adapter
        logger.info(f"Adapter registered: {name} -> {adapter.__class__.__name__}")

    def list_adapters(self) -> dict[str, str]:
        return {k: v.__class__.__name__ for k, v in self._adapters.items()}
