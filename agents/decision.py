"""
ACOE — Decision Agent
Maps detected issues to executable action plans with ROI scoring.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from models.schemas import (
    ActionPlan,
    ActionStatus,
    ActionType,
    DetectedIssue,
    IssueCategory,
    IssueSeverity,
)
import config

logger = logging.getLogger("acoe.decision")


# ── Action Strategy Mapping ──────────────────────────────────────────────────

ACTION_MAP: dict[IssueCategory, list[dict]] = {
    IssueCategory.DUPLICATE_VENDOR: [
        {
            "action_type": ActionType.CONSOLIDATE_VENDORS,
            "title_template": "Consolidate {category} vendors",
            "desc_template": (
                "Consolidate {count} vendors in {category} to single provider. "
                "Negotiate volume discount. Estimated savings: ₹{savings:,.0f}/year."
            ),
            "base_risk": 0.25,
            "base_confidence": 0.85,
        }
    ],
    IssueCategory.SAAS_UNDERUTILIZATION: [
        {
            "action_type": ActionType.DOWNGRADE_PLAN,
            "title_template": "Downgrade {product} to match usage",
            "desc_template": (
                "Reduce {product} from {total} to {needed} licenses. "
                "Save ₹{savings:,.0f}/year by right-sizing the plan."
            ),
            "base_risk": 0.15,
            "base_confidence": 0.90,
        },
        {
            "action_type": ActionType.CANCEL_SUBSCRIPTION,
            "title_template": "Cancel {product} (extremely low usage)",
            "desc_template": (
                "{product} has only {active}/{total} users ({ratio:.0%}). "
                "Consider full cancellation saving ₹{full_cost:,.0f}/year."
            ),
            "base_risk": 0.40,
            "base_confidence": 0.75,
            "condition": lambda issue: issue.evidence.get("utilization", 1) < 0.15,
        },
    ],
    IssueCategory.CLOUD_OVER_PROVISIONING: [
        {
            "action_type": ActionType.REALLOCATE_COMPUTE,
            "title_template": "Right-size {resource} on {provider}",
            "desc_template": (
                "Resize {resource_id} from {capacity} to {target} units. "
                "Maintains peak headroom while saving ₹{savings:,.0f}/year."
            ),
            "base_risk": 0.20,
            "base_confidence": 0.88,
        }
    ],
    IssueCategory.SLA_BREACH_RISK: [
        {
            "action_type": ActionType.TRIGGER_ESCALATION,
            "title_template": "Escalate SLA risk: {service}",
            "desc_template": (
                "SLA breach imminent for {service} ({hours:.0f}h left). "
                "Escalate to vendor {vendor}. Penalty at risk: ₹{penalty:,.0f}."
            ),
            "base_risk": 0.10,
            "base_confidence": 0.95,
        }
    ],
    IssueCategory.COST_ANOMALY: [
        {
            "action_type": ActionType.RENEGOTIATE_CONTRACT,
            "title_template": "Renegotiate pricing for {entity}",
            "desc_template": (
                "Cost of {entity} (₹{cost:,.0f}/mo) is {z:.1f}σ above peer mean. "
                "Renegotiation target: ₹{target:,.0f}/mo saving ₹{savings:,.0f}/year."
            ),
            "base_risk": 0.30,
            "base_confidence": 0.70,
        }
    ],
}


class DecisionAgent:
    """Map detected issues to ranked, executable action plans."""

    def run(self, issues: list[DetectedIssue]) -> list[ActionPlan]:
        logger.info(f"Decision Agent: processing {len(issues)} issues")
        actions: list[ActionPlan] = []

        for issue in issues:
            strategies = ACTION_MAP.get(issue.category, [])
            for strategy in strategies:
                # Check conditional strategies
                condition = strategy.get("condition")
                if condition and not condition(issue):
                    continue

                action = self._build_action(issue, strategy)
                if action:
                    actions.append(action)

        # Rank by net impact (savings * confidence - risk penalty)
        actions.sort(
            key=lambda a: a.estimated_savings_inr * a.confidence_score * (1 - a.risk_score),
            reverse=True,
        )

        # Filter by thresholds
        eligible = [
            a for a in actions
            if a.confidence_score >= config.MIN_CONFIDENCE_TO_ACT
            and a.risk_score <= config.MAX_RISK_TO_ACT
        ]

        logger.info(
            f"Decision Agent: generated {len(actions)} actions, "
            f"{len(eligible)} eligible for execution"
        )
        return eligible

    # ── Private ──────────────────────────────────────────────────────────

    def _build_action(
        self, issue: DetectedIssue, strategy: dict
    ) -> ActionPlan | None:
        try:
            ev = issue.evidence
            savings = issue.potential_savings_inr

            # Build template context
            ctx = {
                "savings": savings,
                "category": ev.get("category", ""),
                "count": len(ev.get("vendors", [])),
                "product": ev.get("product", ""),
                "total": ev.get("total_licenses", 0),
                "needed": ev.get("active_users", 0),
                "active": ev.get("active_users", 0),
                "ratio": ev.get("utilization", 0),
                "full_cost": ev.get("monthly_cost", 0) * 12,
                "resource": ev.get("resource_type", ""),
                "resource_id": issue.affected_entity_id,
                "provider": ev.get("provider", ""),
                "capacity": ev.get("capacity", 0),
                "target": ev.get("peak_usage", 0) * 1.3,  # 30% headroom
                "service": ev.get("service", ""),
                "vendor": ev.get("vendor", ""),
                "hours": ev.get("hours_to_breach", 0),
                "penalty": ev.get("penalty_inr", 0),
                "entity": issue.affected_entity_id,
                "cost": ev.get("cost", 0),
                "z": ev.get("z_score", 0),
                "target_cost": ev.get("mean", 0) * 1.1,
            }
            ctx["target"] = max(ctx.get("target", 0), 1)

            # Adjust risk based on severity
            severity_risk_mod = {
                IssueSeverity.CRITICAL: -0.05,
                IssueSeverity.HIGH: 0.0,
                IssueSeverity.MEDIUM: 0.05,
                IssueSeverity.LOW: 0.10,
            }
            risk = min(
                strategy["base_risk"] + severity_risk_mod.get(issue.severity, 0), 0.95
            )
            confidence = strategy["base_confidence"]

            # ROI = savings / estimated_effort (simplified as savings / 10000)
            roi = savings / max(savings * 0.05, 1)  # 5% implementation cost

            title = strategy["title_template"].format(**ctx)
            desc = strategy["desc_template"].format(**ctx)

            justification = (
                f"Issue [{issue.issue_id}]: {issue.title}. "
                f"Category: {issue.category.value}. Severity: {issue.severity.value}. "
                f"Action: {strategy['action_type'].value}. "
                f"Estimated savings: ₹{savings:,.0f}. "
                f"ROI: {roi:.1f}x. Risk: {risk:.2f}. Confidence: {confidence:.2f}."
            )

            return ActionPlan(
                action_id=f"ACT-{uuid.uuid4().hex[:8].upper()}",
                issue_id=issue.issue_id,
                action_type=strategy["action_type"],
                title=title,
                description=desc,
                target_entity_id=issue.affected_entity_id,
                estimated_savings_inr=savings,
                roi_estimate=round(roi, 2),
                risk_score=round(risk, 3),
                confidence_score=round(confidence, 3),
                justification=justification,
                status=ActionStatus.PENDING,
            )

        except Exception as e:
            logger.error(f"Failed to build action for {issue.issue_id}: {e}")
            return None
