"""
ACOE — Strict Data Models
Pydantic schemas for all entities in the cost optimization pipeline.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    DUPLICATE_VENDOR = "duplicate_vendor"
    SAAS_UNDERUTILIZATION = "saas_underutilization"
    CLOUD_OVER_PROVISIONING = "cloud_over_provisioning"
    SLA_BREACH_RISK = "sla_breach_risk"
    COST_ANOMALY = "cost_anomaly"


class ActionType(str, Enum):
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    DOWNGRADE_PLAN = "downgrade_plan"
    CONSOLIDATE_VENDORS = "consolidate_vendors"
    REALLOCATE_COMPUTE = "reallocate_compute"
    TRIGGER_ESCALATION = "trigger_escalation"
    RENEGOTIATE_CONTRACT = "renegotiate_contract"


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    VERIFIED = "verified"
    SKIPPED = "skipped"


# ── Input Data Models ────────────────────────────────────────────────────────

class ProcurementRecord(BaseModel):
    record_id: str
    vendor_name: str
    service_category: str
    contract_value_inr: float = Field(ge=0)
    contract_start: datetime
    contract_end: datetime
    department: str
    payment_frequency: str = "monthly"
    description: str = ""

class SaaSSubscription(BaseModel):
    subscription_id: str
    vendor_name: str
    product_name: str
    total_licenses: int = Field(ge=0)
    active_users: int = Field(ge=0)
    monthly_cost_inr: float = Field(ge=0)
    plan_tier: str = "standard"
    renewal_date: datetime
    department: str

    @property
    def utilization_ratio(self) -> float:
        if self.total_licenses == 0:
            return 0.0
        return self.active_users / self.total_licenses

class CloudUsage(BaseModel):
    resource_id: str
    provider: str
    resource_type: str
    region: str
    capacity_units: float = Field(ge=0)
    avg_usage_units: float = Field(ge=0)
    peak_usage_units: float = Field(ge=0)
    monthly_cost_inr: float = Field(ge=0)
    department: str

    @property
    def utilization_ratio(self) -> float:
        if self.capacity_units == 0:
            return 0.0
        return self.avg_usage_units / self.capacity_units

class SLAMetric(BaseModel):
    sla_id: str
    service_name: str
    vendor_name: str
    metric_name: str
    target_value: float
    current_value: float
    measurement_unit: str
    breach_penalty_inr: float = Field(ge=0)
    measurement_timestamp: datetime
    breach_deadline: datetime

    @property
    def compliance_ratio(self) -> float:
        if self.target_value == 0:
            return 1.0
        return self.current_value / self.target_value

    @property
    def hours_to_breach(self) -> float:
        delta = self.breach_deadline - self.measurement_timestamp
        return max(delta.total_seconds() / 3600, 0)

# ── Pipeline Output Models ───────────────────────────────────────────────────

class DetectedIssue(BaseModel):
    issue_id: str
    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    affected_entity_id: str
    affected_entity_type: str
    evidence: dict = Field(default_factory=dict)
    potential_savings_inr: float = 0.0
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class ActionPlan(BaseModel):
    action_id: str
    issue_id: str
    action_type: ActionType
    title: str
    description: str
    target_entity_id: str
    estimated_savings_inr: float = 0.0
    roi_estimate: float = 0.0
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    justification: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionLog(BaseModel):
    execution_id: str
    action_id: str
    action_type: ActionType
    status: ActionStatus
    target_entity_id: str
    request_payload: dict = Field(default_factory=dict)
    response_payload: dict = Field(default_factory=dict)
    attempts: int = 0
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = False
    verification_notes: str = ""
    error_message: str = ""


class ImpactReport(BaseModel):
    report_id: str
    cycle_id: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_issues_detected: int = 0
    total_actions_executed: int = 0
    total_actions_verified: int = 0
    realized_savings_inr: float = 0.0
    projected_annual_savings_inr: float = 0.0
    avoided_penalties_inr: float = 0.0
    total_impact_inr: float = 0.0
    breakdown: list[dict] = Field(default_factory=list)
    summary: str = ""


# ── Cycle State ──────────────────────────────────────────────────────────────

class CycleState(BaseModel):
    cycle_id: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    issues_detected: int = 0
    actions_executed: int = 0
    total_savings_inr: float = 0.0
    status: str = "idle"
    errors: list[str] = Field(default_factory=list)


class SystemState(BaseModel):
    total_cycles: int = 0
    last_cycle: Optional[CycleState] = None
    cumulative_savings_inr: float = 0.0
    uptime_start: datetime = Field(default_factory=datetime.utcnow)
    executed_action_keys: list[str] = Field(default_factory=list)
