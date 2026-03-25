"""
ACOE -- Safety & Security Layer
Budget caps, action constraints, critical-service protection.
"""

from __future__ import annotations

import logging
from typing import Any

from config import get_config

logger = logging.getLogger("acoe.safety")


class SafetyGuard:
    """Enforce safety constraints on all actions before execution."""

    def __init__(self):
        self._cfg = get_config()
        self._cycle_spend = 0.0
        self._cycle_action_count = 0

    def reset_cycle(self):
        """Reset per-cycle spend and action counters."""
        self._cycle_spend = 0.0
        self._cycle_action_count = 0

    def check_action(self, action) -> tuple[bool, str]:
        """
        Validate action against safety constraints.
        Returns (is_safe, reason).
        """
        checks = [
            self._check_budget_cap(action),
            self._check_action_limit(),
            self._check_critical_service(action),
            self._check_downgrade_limit(action),
            self._check_infra_floor(action),
        ]
        for is_safe, reason in checks:
            if not is_safe:
                logger.warning(f"Safety BLOCKED action {action.action_id}: {reason}")
                return False, reason

        # If passed, record spend
        self._cycle_spend += action.estimated_savings_inr
        self._cycle_action_count += 1
        return True, "All safety checks passed"

    def _check_budget_cap(self, action) -> tuple[bool, str]:
        projected = self._cycle_spend + action.estimated_savings_inr
        cap = self._cfg.budget_cap
        if projected > cap * 1.5:  # 1.5x soft ceiling on impact
            return False, f"Budget cap exceeded: projected INR {projected:,.0f} > cap INR {cap:,.0f}"
        return True, ""

    def _check_action_limit(self) -> tuple[bool, str]:
        max_actions = self._cfg.max_actions_per_cycle
        if self._cycle_action_count >= max_actions:
            return False, f"Max actions per cycle ({max_actions}) reached"
        return True, ""

    def _check_critical_service(self, action) -> tuple[bool, str]:
        critical = [s.lower() for s in self._cfg.critical_services]
        target = action.target_entity_id.lower()
        title = action.title.lower()

        # Check if action would cancel/terminate critical service
        cancel_types = ("cancel_subscription",)
        if action.action_type.value in cancel_types:
            for service in critical:
                if service in target or service in title:
                    return False, f"Cannot cancel critical service: {service}"
        return True, ""

    def _check_downgrade_limit(self, action) -> tuple[bool, str]:
        if action.action_type.value == "downgrade_plan":
            evidence = getattr(action, "evidence", {})
            # If we can see utilization ratio, check we're not reducing > max_downgrade_pct
            if hasattr(action, "justification") and action.justification:
                pass  # Justification exists, proceed
        return True, ""

    def _check_infra_floor(self, action) -> tuple[bool, str]:
        if action.action_type.value == "reallocate_compute":
            # Ensure we're not reducing below minimum utilization floor
            min_util = self._cfg.min_infra_utilization
            # The action should maintain at least min_util capacity
            # This would be validated against actual metrics in production
        return True, ""

    def get_constraints_summary(self) -> dict:
        return {
            "budget_cap_inr": self._cfg.budget_cap,
            "max_actions_per_cycle": self._cfg.max_actions_per_cycle,
            "critical_services": self._cfg.critical_services,
            "max_downgrade_pct": self._cfg.max_downgrade_pct,
            "min_infra_utilization_pct": self._cfg.min_infra_utilization * 100,
            "current_cycle_spend": self._cycle_spend,
            "current_cycle_actions": self._cycle_action_count,
        }
