"""
ACOE — Verification Layer
Confirms action success by comparing expected vs actual outcomes.
"""

from __future__ import annotations

import logging
from models.schemas import ActionPlan, ActionStatus, ExecutionLog

logger = logging.getLogger("acoe.verification")


class VerificationAgent:
    """Verify execution outcomes and flag mismatches."""

    def run(
        self, actions: list[ActionPlan], execution_logs: list[ExecutionLog]
    ) -> list[ExecutionLog]:
        logger.info(f"Verification Layer: verifying {len(execution_logs)} executions")
        verified_logs = []

        # Map action_id to action for lookup
        action_map = {a.action_id: a for a in actions}

        for log in execution_logs:
            action = action_map.get(log.action_id)
            verified_log = self._verify_single(log, action)
            verified_logs.append(verified_log)

        verified_count = sum(1 for l in verified_logs if l.verified)
        failed_count = sum(1 for l in verified_logs if not l.verified and l.status == ActionStatus.EXECUTED)
        logger.info(
            f"Verification Layer: {verified_count} verified, "
            f"{failed_count} mismatches detected"
        )
        return verified_logs

    def _verify_single(
        self, log: ExecutionLog, action: ActionPlan | None
    ) -> ExecutionLog:
        """Verify a single execution log entry."""
        # Skip verification for non-executed actions
        if log.status in (ActionStatus.SKIPPED, ActionStatus.FAILED):
            log.verified = False
            log.verification_notes = f"Skipped verification — status: {log.status.value}"
            return log

        # Check 1: Response status
        response_status = log.response_payload.get("status", "unknown")
        if response_status != "success":
            log.verified = False
            log.verification_notes = (
                f"MISMATCH: Expected status=success, got status={response_status}"
            )
            log.status = ActionStatus.FAILED
            return log

        # Check 2: Response has meaningful content
        if not log.response_payload.get("message"):
            log.verified = False
            log.verification_notes = "MISMATCH: Response missing confirmation message"
            return log

        # Check 3: Target entity matches
        if action and log.target_entity_id != action.target_entity_id:
            log.verified = False
            log.verification_notes = (
                f"MISMATCH: Target entity mismatch — "
                f"expected {action.target_entity_id}, got {log.target_entity_id}"
            )
            return log

        # Check 4: Verify expected savings alignment (within 20% tolerance)
        if action:
            resp_savings = log.response_payload.get("monthly_savings_inr")
            if resp_savings is not None:
                expected_monthly = action.estimated_savings_inr / 12
                deviation = abs(resp_savings - expected_monthly) / max(expected_monthly, 1)
                if deviation > 0.20:
                    log.verified = True  # still mark verified but flag
                    log.verification_notes = (
                        f"WARNING: Savings deviation {deviation:.0%} — "
                        f"expected ₹{expected_monthly:,.0f}/mo, got ₹{resp_savings:,.0f}/mo"
                    )
                    return log

        # All checks passed
        log.verified = True
        log.status = ActionStatus.VERIFIED
        log.verification_notes = "All verification checks passed"
        return log
