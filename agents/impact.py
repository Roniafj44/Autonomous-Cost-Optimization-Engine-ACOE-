"""
ACOE — Impact Agent
Computes realized savings, projected savings, and avoided SLA penalties in ₹.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from models.schemas import (
    ActionPlan,
    ActionStatus,
    ExecutionLog,
    ImpactReport,
    IssueCategory,
)
import config

logger = logging.getLogger("acoe.impact")


class ImpactAgent:
    """Quantify financial impact of all executed actions."""

    def run(
        self,
        cycle_id: int,
        actions: list[ActionPlan],
        execution_logs: list[ExecutionLog],
        issues: list,
    ) -> ImpactReport:
        logger.info(f"Impact Agent: computing financial impact for cycle {cycle_id}")

        # Build lookup maps
        action_map = {a.action_id: a for a in actions}
        issue_map = {i.issue_id: i for i in issues}

        realized = 0.0
        projected = 0.0
        avoided_penalties = 0.0
        breakdown = []

        for log in execution_logs:
            action = action_map.get(log.action_id)
            if not action:
                continue

            issue = issue_map.get(action.issue_id)
            is_executed = log.status in (ActionStatus.EXECUTED, ActionStatus.VERIFIED)

            if not is_executed:
                continue

            savings = action.estimated_savings_inr
            time_horizon = config.DEFAULT_TIME_HORIZON_MONTHS

            # Categorize savings
            if issue and issue.category == IssueCategory.SLA_BREACH_RISK:
                # SLA penalty avoidance
                penalty = issue.evidence.get("penalty_inr", 0)
                avoided_penalties += penalty
                breakdown.append({
                    "action_id": action.action_id,
                    "type": "avoided_penalty",
                    "category": issue.category.value,
                    "description": action.title,
                    "amount_inr": penalty,
                    "period": "one-time",
                })
            else:
                # Cost savings (realized = first month, projected = annual)
                monthly_savings = savings / 12
                realized += monthly_savings
                projected += savings

                breakdown.append({
                    "action_id": action.action_id,
                    "type": "cost_reduction",
                    "category": issue.category.value if issue else "unknown",
                    "description": action.title,
                    "monthly_savings_inr": round(monthly_savings, 2),
                    "annual_savings_inr": round(savings, 2),
                    "period": f"{time_horizon} months",
                })

        total_impact = realized + projected + avoided_penalties

        report = ImpactReport(
            report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
            cycle_id=cycle_id,
            generated_at=datetime.utcnow(),
            total_issues_detected=len(issues),
            total_actions_executed=sum(
                1 for l in execution_logs
                if l.status in (ActionStatus.EXECUTED, ActionStatus.VERIFIED)
            ),
            total_actions_verified=sum(1 for l in execution_logs if l.verified),
            realized_savings_inr=round(realized, 2),
            projected_annual_savings_inr=round(projected, 2),
            avoided_penalties_inr=round(avoided_penalties, 2),
            total_impact_inr=round(total_impact, 2),
            breakdown=breakdown,
            summary=self._build_summary(realized, projected, avoided_penalties, total_impact),
        )

        logger.info(
            f"Impact Agent: Total impact ₹{total_impact:,.0f} — "
            f"Realized: ₹{realized:,.0f}, Projected: ₹{projected:,.0f}, "
            f"Avoided penalties: ₹{avoided_penalties:,.0f}"
        )
        return report

    def _build_summary(
        self, realized: float, projected: float, avoided: float, total: float
    ) -> str:
        parts = []
        if realized > 0:
            parts.append(f"Realized monthly savings: ₹{realized:,.0f}")
        if projected > 0:
            parts.append(f"Projected annual savings: ₹{projected:,.0f}")
        if avoided > 0:
            parts.append(f"SLA penalties avoided: ₹{avoided:,.0f}")
        parts.append(f"Total financial impact: ₹{total:,.0f}")
        return " | ".join(parts)
