"""
ACOE — Execution Agent
Executes action plans via mock APIs with retry logic and idempotency.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta

from models.schemas import (
    ActionPlan,
    ActionStatus,
    ActionType,
    ExecutionLog,
)
import config

logger = logging.getLogger("acoe.execution")


class ExecutionAgent:
    """Execute action plans with mock APIs, retry logic, and idempotency."""

    def __init__(self):
        self._executed_keys: set[str] = set()

    def load_executed_keys(self, keys: list[str]):
        """Restore idempotency state from system state."""
        self._executed_keys = set(keys)

    def get_executed_keys(self) -> list[str]:
        return list(self._executed_keys)

    def run(self, actions: list[ActionPlan]) -> list[ExecutionLog]:
        logger.info(f"Execution Agent: processing {len(actions)} actions")
        logs: list[ExecutionLog] = []

        for action in actions:
            # Check approval gate
            if config.APPROVAL_GATE_ENABLED:
                action.status = ActionStatus.PENDING
                logger.info(f"Action {action.action_id} queued for approval (gate enabled)")
                logs.append(self._create_log(action, ActionStatus.SKIPPED, 0, "Approval gate enabled"))
                continue

            # Idempotency check
            dedup_key = self._dedup_key(action)
            if dedup_key in self._executed_keys:
                logger.info(f"Action {action.action_id} skipped (already executed)")
                logs.append(self._create_log(action, ActionStatus.SKIPPED, 0, "Idempotent skip"))
                continue

            # Execute with retry
            log = self._execute_with_retry(action)
            if log.status == ActionStatus.EXECUTED:
                self._executed_keys.add(dedup_key)
                action.status = ActionStatus.EXECUTED
            else:
                action.status = ActionStatus.FAILED

            logs.append(log)

        executed_count = sum(1 for l in logs if l.status == ActionStatus.EXECUTED)
        logger.info(
            f"Execution Agent: {executed_count}/{len(logs)} actions executed successfully"
        )
        return logs

    # ── Retry Logic ──────────────────────────────────────────────────────

    def _execute_with_retry(self, action: ActionPlan) -> ExecutionLog:
        last_error = ""
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                result = self._mock_execute(action)
                return ExecutionLog(
                    execution_id=f"EXEC-{uuid.uuid4().hex[:8].upper()}",
                    action_id=action.action_id,
                    action_type=action.action_type,
                    status=ActionStatus.EXECUTED,
                    target_entity_id=action.target_entity_id,
                    request_payload=self._build_request(action),
                    response_payload=result,
                    attempts=attempt,
                    executed_at=datetime.utcnow(),
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Attempt {attempt}/{config.MAX_RETRIES} failed for "
                    f"{action.action_id}: {e}"
                )
                if attempt < config.MAX_RETRIES:
                    backoff = config.RETRY_BACKOFF_BASE ** attempt
                    time.sleep(min(backoff, 5))  # cap at 5s for demo

        return ExecutionLog(
            execution_id=f"EXEC-{uuid.uuid4().hex[:8].upper()}",
            action_id=action.action_id,
            action_type=action.action_type,
            status=ActionStatus.FAILED,
            target_entity_id=action.target_entity_id,
            request_payload=self._build_request(action),
            response_payload={"error": last_error},
            attempts=config.MAX_RETRIES,
            executed_at=datetime.utcnow(),
            error_message=last_error,
        )

    # ── Mock Execution Endpoints ─────────────────────────────────────────

    def _mock_execute(self, action: ActionPlan) -> dict:
        """Simulate API call for each action type."""
        handlers = {
            ActionType.CANCEL_SUBSCRIPTION: self._mock_cancel,
            ActionType.DOWNGRADE_PLAN: self._mock_downgrade,
            ActionType.CONSOLIDATE_VENDORS: self._mock_consolidate,
            ActionType.REALLOCATE_COMPUTE: self._mock_reallocate,
            ActionType.TRIGGER_ESCALATION: self._mock_escalation,
            ActionType.RENEGOTIATE_CONTRACT: self._mock_renegotiate,
        }
        handler = handlers.get(action.action_type, self._mock_generic)
        return handler(action)

    def _mock_cancel(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Subscription {action.target_entity_id} cancelled",
            "effective_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "refund_eligible": True,
        }

    def _mock_downgrade(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Plan downgraded for {action.target_entity_id}",
            "new_tier": "reduced",
            "effective_date": datetime.utcnow().isoformat(),
            "monthly_savings_inr": action.estimated_savings_inr / 12,
        }

    def _mock_consolidate(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Vendor consolidation initiated for {action.target_entity_id}",
            "consolidation_plan": "transition_to_primary_vendor",
            "estimated_completion": (datetime.utcnow() + timedelta(days=90)).isoformat(),
        }

    def _mock_reallocate(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Resource {action.target_entity_id} right-sized",
            "new_capacity": "optimized",
            "effective_date": datetime.utcnow().isoformat(),
        }

    def _mock_escalation(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"SLA escalation triggered for {action.target_entity_id}",
            "ticket_id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
            "priority": "critical",
            "assigned_to": "vendor_account_manager",
        }

    def _mock_renegotiate(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Renegotiation request sent for {action.target_entity_id}",
            "proposal_id": f"NEG-{uuid.uuid4().hex[:6].upper()}",
            "target_reduction_pct": 15,
        }

    def _mock_generic(self, action: ActionPlan) -> dict:
        return {
            "status": "success",
            "message": f"Action {action.action_type.value} executed for {action.target_entity_id}",
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    def _build_request(self, action: ActionPlan) -> dict:
        return {
            "action_type": action.action_type.value,
            "target": action.target_entity_id,
            "estimated_savings": action.estimated_savings_inr,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _dedup_key(self, action: ActionPlan) -> str:
        raw = f"{action.action_type.value}:{action.target_entity_id}:{action.issue_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _create_log(
        self, action: ActionPlan, status: ActionStatus, attempts: int, note: str
    ) -> ExecutionLog:
        return ExecutionLog(
            execution_id=f"EXEC-{uuid.uuid4().hex[:8].upper()}",
            action_id=action.action_id,
            action_type=action.action_type,
            status=status,
            target_entity_id=action.target_entity_id,
            request_payload=self._build_request(action),
            response_payload={"note": note},
            attempts=attempts,
            executed_at=datetime.utcnow(),
            verification_notes=note,
        )
