"""
ACOE -- Metrics Tracker
Tracks and exposes system-wide performance metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("acoe.metrics")


class MetricsTracker:
    """In-memory + persisted metrics for system observability."""

    def __init__(self, state_manager=None):
        self._state = state_manager
        self._current: dict[str, float] = {}
        self._history: list[dict] = []

    def record_cycle(self, cycle_id: int, issues: list, actions: list,
                     exec_logs: list, report):
        """Record all metrics for a completed cycle."""
        executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
        failed = sum(1 for l in exec_logs if l.status.value == "failed")
        verified = sum(1 for l in exec_logs if l.verified)
        total = len(exec_logs)

        savings = report.total_impact_inr if report else 0
        avg_roi = 0
        if actions:
            avg_roi = sum(a.roi_estimate for a in actions) / len(actions)

        sla_avoided = sum(
            1 for i in issues
            if hasattr(i, 'category') and i.category.value == "sla_breach_risk"
        )

        metrics = {
            "total_savings_inr": savings,
            "issues_detected": len(issues),
            "actions_planned": len(actions),
            "actions_executed": executed,
            "actions_failed": failed,
            "actions_verified": verified,
            "success_rate": (executed / max(total, 1)) * 100,
            "verification_rate": (verified / max(executed, 1)) * 100,
            "avg_roi": round(avg_roi, 2),
            "avg_risk": round(sum(a.risk_score for a in actions) / max(len(actions), 1), 4),
            "avg_confidence": round(sum(a.confidence_score for a in actions) / max(len(actions), 1), 4),
            "sla_risks_avoided": sla_avoided,
            "realized_savings_inr": report.realized_savings_inr if report else 0,
            "projected_savings_inr": report.projected_annual_savings_inr if report else 0,
            "avoided_penalties_inr": report.avoided_penalties_inr if report else 0,
        }

        self._current = metrics

        # Persist to DB if available
        if self._state:
            for name, value in metrics.items():
                try:
                    self._state.save_metric(cycle_id, name, value)
                except Exception:
                    pass

        # Keep in-memory history
        entry = {"cycle_id": cycle_id, "timestamp": datetime.utcnow().isoformat()}
        entry.update(metrics)
        self._history.append(entry)

        logger.info(
            f"Metrics recorded for cycle {cycle_id}: "
            f"savings=INR {savings:,.0f}, executed={executed}/{total}, "
            f"success={metrics['success_rate']:.0f}%, roi={avg_roi:.1f}x"
        )

    def get_current(self) -> dict:
        return dict(self._current)

    def get_history(self) -> list[dict]:
        return list(self._history)

    def get_cumulative(self) -> dict:
        """Aggregate metrics across all cycles."""
        if not self._history:
            return {"status": "no_data"}

        return {
            "total_cycles": len(self._history),
            "total_savings_inr": sum(h.get("total_savings_inr", 0) for h in self._history),
            "total_issues": sum(h.get("issues_detected", 0) for h in self._history),
            "total_actions_executed": sum(h.get("actions_executed", 0) for h in self._history),
            "total_actions_failed": sum(h.get("actions_failed", 0) for h in self._history),
            "overall_success_rate": round(
                sum(h.get("success_rate", 0) for h in self._history) / len(self._history), 1
            ),
            "overall_avg_roi": round(
                sum(h.get("avg_roi", 0) for h in self._history) / len(self._history), 2
            ),
            "total_sla_risks_avoided": sum(h.get("sla_risks_avoided", 0) for h in self._history),
        }
