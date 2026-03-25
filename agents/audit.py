"""
ACOE — Audit Agent
Logs ALL decisions, reasoning, and actions for full auditability.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger("acoe.audit")


class AuditAgent:
    """Write structured JSON + human-readable audit logs per cycle."""

    def __init__(self):
        self.logs_dir = config.LOGS_DIR
        os.makedirs(self.logs_dir, exist_ok=True)

    def run(
        self,
        cycle_id: int,
        ingested_data: dict,
        issues: list,
        actions: list,
        execution_logs: list,
        impact_report,
    ) -> str:
        """
        Write complete audit log for a cycle.
        Returns path to the JSON log file.
        """
        logger.info(f"Audit Agent: writing logs for cycle {cycle_id}")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"cycle_{cycle_id:04d}_{timestamp}.json"
        filepath = os.path.join(self.logs_dir, filename)

        audit_record = {
            "cycle_id": cycle_id,
            "timestamp": datetime.utcnow().isoformat(),
            "input_summary": self._summarize_input(ingested_data),
            "detection": {
                "total_issues": len(issues),
                "issues": [self._serialize(i) for i in issues],
            },
            "decisions": {
                "total_actions": len(actions),
                "actions": [self._serialize(a) for a in actions],
            },
            "execution": {
                "total_executions": len(execution_logs),
                "logs": [self._serialize(l) for l in execution_logs],
            },
            "impact": self._serialize(impact_report) if impact_report else None,
            "human_readable_summary": self._generate_summary(
                cycle_id, issues, actions, execution_logs, impact_report
            ),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(audit_record, f, indent=2, default=str, ensure_ascii=False)
            logger.info(f"Audit Agent: log written to {filepath}")
        except Exception as e:
            logger.error(f"Audit Agent: failed to write log — {e}")
            filepath = ""

        # Also write the human-readable summary
        summary_path = os.path.join(
            self.logs_dir, f"summary_{cycle_id:04d}_{timestamp}.txt"
        )
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(audit_record["human_readable_summary"])
        except Exception as e:
            logger.warning(f"Audit Agent: failed to write summary — {e}")

        return filepath

    def get_latest_log(self) -> dict | None:
        """Read the most recent audit log."""
        try:
            files = sorted(
                [f for f in os.listdir(self.logs_dir) if f.endswith(".json")],
                reverse=True,
            )
            if not files:
                return None
            path = os.path.join(self.logs_dir, files[0])
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ── Serialization ────────────────────────────────────────────────────

    def _serialize(self, obj) -> dict:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "dict"):
            return obj.dict()
        return {"value": str(obj)}

    def _summarize_input(self, data: dict) -> dict:
        return {
            "procurement_records": len(data.get("procurement", [])),
            "saas_subscriptions": len(data.get("saas", [])),
            "cloud_resources": len(data.get("cloud", [])),
            "sla_metrics": len(data.get("sla", [])),
            "total_records": sum(len(v) for v in data.values()),
        }

    # ── Human-Readable Summary ───────────────────────────────────────────

    def _generate_summary(
        self, cycle_id, issues, actions, execution_logs, impact_report
    ) -> str:
        lines = [
            "=" * 70,
            f"  ACOE AUTONOMOUS CYCLE REPORT — Cycle #{cycle_id}",
            f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 70,
            "",
            f"📊 DETECTION SUMMARY",
            f"   Total issues detected: {len(issues)}",
        ]

        # Group issues by category
        from collections import Counter
        cat_counts = Counter(i.category.value if hasattr(i, 'category') else 'unknown' for i in issues)
        for cat, count in cat_counts.most_common():
            lines.append(f"   • {cat}: {count}")

        lines.extend([
            "",
            f"🎯 DECISION SUMMARY",
            f"   Actions planned: {len(actions)}",
        ])
        for action in actions[:5]:
            sav = action.estimated_savings_inr if hasattr(action, 'estimated_savings_inr') else 0
            title = action.title if hasattr(action, 'title') else str(action)
            lines.append(f"   • {title} → ₹{sav:,.0f} savings")

        executed = [l for l in execution_logs if hasattr(l, 'status') and l.status.value in ('executed', 'verified')]
        lines.extend([
            "",
            f"⚡ EXECUTION SUMMARY",
            f"   Executed: {len(executed)}/{len(execution_logs)}",
        ])

        if impact_report and hasattr(impact_report, 'total_impact_inr'):
            lines.extend([
                "",
                f"💰 FINANCIAL IMPACT",
                f"   Realized savings:  ₹{impact_report.realized_savings_inr:,.0f}",
                f"   Projected annual:  ₹{impact_report.projected_annual_savings_inr:,.0f}",
                f"   Avoided penalties: ₹{impact_report.avoided_penalties_inr:,.0f}",
                f"   ─────────────────────────────",
                f"   TOTAL IMPACT:      ₹{impact_report.total_impact_inr:,.0f}",
            ])

        lines.extend(["", "=" * 70])
        return "\n".join(lines)
