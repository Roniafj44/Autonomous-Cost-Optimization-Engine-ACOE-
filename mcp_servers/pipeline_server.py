"""
ACOE — Pipeline MCP Server
===========================
Exposes the 7-stage ACOE autonomous pipeline as individual MCP tools.

Tools:
  - acoe_ingest:          Stage 1 — Load & validate enterprise data
  - acoe_detect:          Stage 2 — Detect cost inefficiencies
  - acoe_decide:          Stage 3 — Generate action plans with ROI scoring
  - acoe_execute:         Stage 4 — Execute actions autonomously
  - acoe_verify:          Stage 5 — 4-point outcome verification
  - acoe_audit:           Stage 6 — Write immutable audit trail
  - acoe_impact:          Stage 7 — Compute financial impact report
  - acoe_run_full_cycle:  Run all 7 stages end-to-end

Usage:
  python mcp_servers/pipeline_server.py

All tools are defensively coded — no tool call will ever crash the server.
"""

from __future__ import annotations

import os
import sys
import logging
import traceback
from datetime import datetime

# ── Ensure ACOE root is importable ──────────────────────────────────────────
ACOE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ACOE_ROOT not in sys.path:
    sys.path.insert(0, ACOE_ROOT)

from mcp_servers.base import MCPBaseServer
from mcp_servers.utils import safe_serialize, safe_call, format_inr

logger = logging.getLogger("acoe.mcp.pipeline")


# ── Session State ────────────────────────────────────────────────────────────
# Holds data between individual stage calls within the same session.
# This allows calling stages independently (acoe_ingest → acoe_detect → ...)
# without losing intermediate results.

class PipelineSession:
    """In-memory session state for a pipeline run."""

    def __init__(self):
        self.data = {}          # Stage 1 output: ingested data
        self.issues = []        # Stage 2 output: detected issues
        self.actions = []       # Stage 3 output: action plans
        self.exec_logs = []     # Stage 4 output: execution logs
        self.verified_logs = [] # Stage 5 output: verified logs
        self.audit_path = ""    # Stage 6 output: audit log path
        self.report = None      # Stage 7 output: impact report
        self.cycle_id = 1
        self.last_run = None

    def reset(self):
        self.__init__()


_session = PipelineSession()


# ── Agent Lazy Loaders ───────────────────────────────────────────────────────
# Agents are imported lazily to avoid import errors at server startup.
# If ACOE core has issues, the error is caught and reported per-tool.

def _get_ingestion_agent():
    from agents.ingestion import IngestionAgent
    return IngestionAgent()

def _get_detection_agent():
    from agents.detection import DetectionAgent
    return DetectionAgent()

def _get_decision_agent():
    from agents.decision import DecisionAgent
    return DecisionAgent()

def _get_execution_agent():
    from agents.execution import ExecutionAgent
    return ExecutionAgent()

def _get_verification_agent():
    from agents.verification import VerificationAgent
    return VerificationAgent()

def _get_audit_agent():
    from agents.audit import AuditAgent
    return AuditAgent()

def _get_impact_agent():
    from agents.impact import ImpactAgent
    return ImpactAgent()


# ── Create the MCP Server ───────────────────────────────────────────────────

server = MCPBaseServer(
    name="acoe-pipeline",
    version="1.0.0",
    description="ACOE 7-Stage Autonomous Cost Optimization Pipeline",
)


# ── Tool: acoe_ingest ───────────────────────────────────────────────────────

@server.tool(
    name="acoe_ingest",
    description=(
        "Stage 1: INGESTION — Load and validate enterprise data from CSV sources. "
        "Reads procurement, SaaS subscriptions, cloud usage, and SLA metrics. "
        "Returns record counts per category. No input required."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def acoe_ingest() -> dict:
    """Run the data ingestion stage."""
    try:
        agent = _get_ingestion_agent()
        data = agent.run()
        _session.data = data
        _session.last_run = datetime.utcnow().isoformat()

        return {
            "success": True,
            "stage": "1_INGESTION",
            "summary": {
                "procurement_records": len(data.get("procurement", [])),
                "saas_subscriptions": len(data.get("saas", [])),
                "cloud_resources": len(data.get("cloud", [])),
                "sla_metrics": len(data.get("sla", [])),
                "total_records": sum(len(v) for v in data.values()),
            },
            "stats": safe_serialize(agent.get_stats()),
            "message": f"Successfully ingested {sum(len(v) for v in data.values())} records from 4 sources",
        }
    except Exception as e:
        logger.error(f"Ingestion failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "1_INGESTION",
            "error": str(e),
            "error_type": type(e).__name__,
            "message": "Data ingestion failed. Check that CSV files exist in the data/ directory.",
        }


# ── Tool: acoe_detect ───────────────────────────────────────────────────────

@server.tool(
    name="acoe_detect",
    description=(
        "Stage 2: DETECTION — Analyze ingested data to detect cost inefficiencies. "
        "Uses rule-based heuristics and z-score anomaly detection. "
        "Requires Stage 1 (ingest) to have run first, or will auto-run it."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "auto_ingest": {
                "type": "boolean",
                "description": "If true (default), auto-run ingestion if no data is available",
                "default": True,
            }
        },
        "additionalProperties": False,
    },
)
def acoe_detect(auto_ingest: bool = True) -> dict:
    """Run the detection stage."""
    try:
        # Auto-ingest if no data available
        if not _session.data and auto_ingest:
            logger.info("No ingested data found, auto-running ingestion")
            ingest_result = acoe_ingest()
            if not ingest_result.get("success"):
                return {
                    "success": False,
                    "stage": "2_DETECTION",
                    "error": "Auto-ingestion failed",
                    "ingest_error": ingest_result.get("error"),
                }

        if not _session.data:
            return {
                "success": False,
                "stage": "2_DETECTION",
                "error": "No ingested data available. Run acoe_ingest first.",
            }

        agent = _get_detection_agent()
        issues = agent.run(_session.data)
        _session.issues = issues

        # Build summary
        severity_counts = {}
        category_counts = {}
        total_potential_savings = 0.0

        for issue in issues:
            sev = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
            cat = issue.category.value if hasattr(issue.category, "value") else str(issue.category)
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            category_counts[cat] = category_counts.get(cat, 0) + 1
            total_potential_savings += getattr(issue, "potential_savings_inr", 0)

        return {
            "success": True,
            "stage": "2_DETECTION",
            "total_issues": len(issues),
            "by_severity": severity_counts,
            "by_category": category_counts,
            "total_potential_savings_inr": round(total_potential_savings, 2),
            "total_potential_savings_formatted": format_inr(total_potential_savings),
            "issues": [
                {
                    "id": issue.issue_id,
                    "category": issue.category.value if hasattr(issue.category, "value") else str(issue.category),
                    "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
                    "title": issue.title,
                    "potential_savings_inr": getattr(issue, "potential_savings_inr", 0),
                    "affected_entity": getattr(issue, "affected_entity_id", ""),
                }
                for issue in issues
            ],
            "message": f"Detected {len(issues)} inefficiencies with {format_inr(total_potential_savings)} in potential savings",
        }
    except Exception as e:
        logger.error(f"Detection failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "2_DETECTION",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_decide ───────────────────────────────────────────────────────

@server.tool(
    name="acoe_decide",
    description=(
        "Stage 3: DECISION — Generate ranked action plans from detected issues. "
        "Each action includes confidence score, risk score, and ROI estimate. "
        "Requires Stage 2 (detect) to have run first, or will auto-run stages 1-2."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "auto_detect": {
                "type": "boolean",
                "description": "If true (default), auto-run detection if no issues are available",
                "default": True,
            }
        },
        "additionalProperties": False,
    },
)
def acoe_decide(auto_detect: bool = True) -> dict:
    """Run the decision stage."""
    try:
        if not _session.issues and auto_detect:
            logger.info("No issues found, auto-running detection")
            detect_result = acoe_detect(auto_ingest=True)
            if not detect_result.get("success"):
                return {
                    "success": False,
                    "stage": "3_DECISION",
                    "error": "Auto-detection failed",
                    "detect_error": detect_result.get("error"),
                }

        if not _session.issues:
            return {
                "success": False,
                "stage": "3_DECISION",
                "error": "No issues available. Run acoe_detect first.",
            }

        agent = _get_decision_agent()
        actions = agent.run(_session.issues)
        _session.actions = actions

        total_savings = sum(getattr(a, "estimated_savings_inr", 0) for a in actions)

        return {
            "success": True,
            "stage": "3_DECISION",
            "total_actions": len(actions),
            "total_estimated_savings_inr": round(total_savings, 2),
            "total_estimated_savings_formatted": format_inr(total_savings),
            "actions": [
                {
                    "id": a.action_id,
                    "type": a.action_type.value if hasattr(a.action_type, "value") else str(a.action_type),
                    "title": a.title,
                    "estimated_savings_inr": a.estimated_savings_inr,
                    "confidence": round(a.confidence_score, 3),
                    "risk": round(a.risk_score, 3),
                    "roi": round(a.roi_estimate, 2),
                    "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                }
                for a in actions
            ],
            "message": f"Generated {len(actions)} action plans with {format_inr(total_savings)} estimated savings",
        }
    except Exception as e:
        logger.error(f"Decision failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "3_DECISION",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_execute ──────────────────────────────────────────────────────

@server.tool(
    name="acoe_execute",
    description=(
        "Stage 4: EXECUTION — Execute approved action plans autonomously. "
        "Uses retry logic and idempotency to ensure safe execution. "
        "Requires Stage 3 (decide) to have run first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "auto_decide": {
                "type": "boolean",
                "description": "If true (default), auto-run decision if no actions are available",
                "default": True,
            }
        },
        "additionalProperties": False,
    },
)
def acoe_execute(auto_decide: bool = True) -> dict:
    """Run the execution stage."""
    try:
        if not _session.actions and auto_decide:
            logger.info("No actions found, auto-running decision")
            decide_result = acoe_decide(auto_detect=True)
            if not decide_result.get("success"):
                return {
                    "success": False,
                    "stage": "4_EXECUTION",
                    "error": "Auto-decision failed",
                    "decide_error": decide_result.get("error"),
                }

        if not _session.actions:
            return {
                "success": False,
                "stage": "4_EXECUTION",
                "error": "No actions available. Run acoe_decide first.",
            }

        agent = _get_execution_agent()
        exec_logs = agent.run(_session.actions)
        _session.exec_logs = exec_logs

        executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
        failed = sum(1 for l in exec_logs if l.status.value == "failed")
        skipped = sum(1 for l in exec_logs if l.status.value == "skipped")

        return {
            "success": True,
            "stage": "4_EXECUTION",
            "total_executions": len(exec_logs),
            "executed": executed,
            "failed": failed,
            "skipped": skipped,
            "executions": [
                {
                    "id": l.execution_id,
                    "action_id": l.action_id,
                    "status": l.status.value if hasattr(l.status, "value") else str(l.status),
                    "attempts": l.attempts,
                    "target": l.target_entity_id,
                    "error": l.error_message or None,
                }
                for l in exec_logs
            ],
            "message": f"Executed {executed}/{len(exec_logs)} actions ({failed} failed, {skipped} skipped)",
        }
    except Exception as e:
        logger.error(f"Execution failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "4_EXECUTION",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_verify ───────────────────────────────────────────────────────

@server.tool(
    name="acoe_verify",
    description=(
        "Stage 5: VERIFICATION — Run 4-point outcome verification on executed actions. "
        "Checks response status, content, entity match, and savings alignment. "
        "Requires Stage 4 (execute) to have run first."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def acoe_verify() -> dict:
    """Run the verification stage."""
    try:
        if not _session.exec_logs:
            return {
                "success": False,
                "stage": "5_VERIFICATION",
                "error": "No execution logs available. Run acoe_execute first.",
            }

        agent = _get_verification_agent()
        verified_logs = agent.run(_session.actions, _session.exec_logs)
        _session.verified_logs = verified_logs

        verified_count = sum(1 for l in verified_logs if l.verified)
        mismatch_count = sum(1 for l in verified_logs if not l.verified and l.status.value == "executed")

        return {
            "success": True,
            "stage": "5_VERIFICATION",
            "total_checked": len(verified_logs),
            "verified": verified_count,
            "mismatches": mismatch_count,
            "results": [
                {
                    "execution_id": l.execution_id,
                    "action_id": l.action_id,
                    "verified": l.verified,
                    "status": l.status.value if hasattr(l.status, "value") else str(l.status),
                    "notes": l.verification_notes,
                }
                for l in verified_logs
            ],
            "message": f"Verified {verified_count}/{len(verified_logs)} executions ({mismatch_count} mismatches)",
        }
    except Exception as e:
        logger.error(f"Verification failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "5_VERIFICATION",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_audit ────────────────────────────────────────────────────────

@server.tool(
    name="acoe_audit",
    description=(
        "Stage 6: AUDIT — Write the complete decision audit trail to an immutable log file. "
        "Logs all decisions, reasoning, actions, and outcomes for full auditability. "
        "Returns the path to the generated audit log file."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def acoe_audit() -> dict:
    """Run the audit stage."""
    try:
        agent = _get_audit_agent()
        logs_to_use = _session.verified_logs or _session.exec_logs
        log_path = agent.run(
            _session.cycle_id,
            _session.data or {"procurement": [], "saas": [], "cloud": [], "sla": []},
            _session.issues or [],
            _session.actions or [],
            logs_to_use,
            _session.report,
        )

        _session.audit_path = log_path

        return {
            "success": True,
            "stage": "6_AUDIT",
            "log_path": log_path,
            "cycle_id": _session.cycle_id,
            "message": f"Audit log written to {log_path}",
        }
    except Exception as e:
        logger.error(f"Audit failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "6_AUDIT",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_impact ───────────────────────────────────────────────────────

@server.tool(
    name="acoe_impact",
    description=(
        "Stage 7: IMPACT — Compute the financial impact report. "
        "Calculates realized savings, projected annual savings, and avoided SLA penalties. "
        "Generates a BEFORE vs AFTER financial comparison in INR."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
def acoe_impact() -> dict:
    """Run the impact analysis stage."""
    try:
        if not _session.actions:
            return {
                "success": False,
                "stage": "7_IMPACT",
                "error": "No actions available. Run the pipeline first.",
            }

        agent = _get_impact_agent()
        logs_to_use = _session.verified_logs or _session.exec_logs or []
        report = agent.run(
            _session.cycle_id,
            _session.actions,
            logs_to_use,
            _session.issues,
        )
        _session.report = report

        return {
            "success": True,
            "stage": "7_IMPACT",
            "report": {
                "report_id": report.report_id,
                "cycle_id": report.cycle_id,
                "total_issues_detected": report.total_issues_detected,
                "total_actions_executed": report.total_actions_executed,
                "total_actions_verified": report.total_actions_verified,
                "realized_savings_inr": report.realized_savings_inr,
                "realized_savings_formatted": format_inr(report.realized_savings_inr),
                "projected_annual_savings_inr": report.projected_annual_savings_inr,
                "projected_annual_savings_formatted": format_inr(report.projected_annual_savings_inr),
                "avoided_penalties_inr": report.avoided_penalties_inr,
                "avoided_penalties_formatted": format_inr(report.avoided_penalties_inr),
                "total_impact_inr": report.total_impact_inr,
                "total_impact_formatted": format_inr(report.total_impact_inr),
                "summary": report.summary,
                "breakdown": safe_serialize(report.breakdown),
            },
            "message": f"Total financial impact: {format_inr(report.total_impact_inr)}",
        }
    except Exception as e:
        logger.error(f"Impact analysis failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "stage": "7_IMPACT",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ── Tool: acoe_run_full_cycle ────────────────────────────────────────────────

@server.tool(
    name="acoe_run_full_cycle",
    description=(
        "Run all 7 stages of the ACOE pipeline end-to-end in a single call. "
        "This is the fastest way to get a complete optimization analysis. "
        "Returns the full cycle results including financial impact report."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reset_session": {
                "type": "boolean",
                "description": "If true (default), reset session state before running",
                "default": True,
            }
        },
        "additionalProperties": False,
    },
)
def acoe_run_full_cycle(reset_session: bool = True) -> dict:
    """Run all 7 stages sequentially."""
    try:
        if reset_session:
            _session.reset()

        stages = [
            ("1_INGESTION", acoe_ingest, {}),
            ("2_DETECTION", acoe_detect, {"auto_ingest": False}),
            ("3_DECISION", acoe_decide, {"auto_detect": False}),
            ("4_EXECUTION", acoe_execute, {"auto_decide": False}),
            ("5_VERIFICATION", acoe_verify, {}),
            ("7_IMPACT", acoe_impact, {}),
            ("6_AUDIT", acoe_audit, {}),
        ]

        results = {}
        errors = []

        for stage_name, stage_func, kwargs in stages:
            try:
                result = stage_func(**kwargs)
                results[stage_name] = result
                if not result.get("success"):
                    errors.append(f"{stage_name}: {result.get('error', 'Unknown error')}")
                    # Continue to next stage — don't abort the whole pipeline
            except Exception as e:
                error_msg = f"{stage_name}: {e}"
                errors.append(error_msg)
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }

        # Build summary
        impact_result = results.get("7_IMPACT", {})
        report_data = impact_result.get("report", {})

        return {
            "success": len(errors) == 0,
            "cycle_id": _session.cycle_id,
            "stages_completed": sum(1 for r in results.values() if r.get("success")),
            "stages_total": len(stages),
            "errors": errors if errors else None,
            "financial_impact": {
                "total_impact_inr": report_data.get("total_impact_inr", 0),
                "total_impact_formatted": report_data.get("total_impact_formatted", "₹0"),
                "realized_savings": report_data.get("realized_savings_formatted", "₹0"),
                "projected_annual": report_data.get("projected_annual_savings_formatted", "₹0"),
                "avoided_penalties": report_data.get("avoided_penalties_formatted", "₹0"),
            },
            "summary": {
                "records_ingested": results.get("1_INGESTION", {}).get("summary", {}).get("total_records", 0),
                "issues_detected": results.get("2_DETECTION", {}).get("total_issues", 0),
                "actions_planned": results.get("3_DECISION", {}).get("total_actions", 0),
                "actions_executed": results.get("4_EXECUTION", {}).get("executed", 0),
                "actions_verified": results.get("5_VERIFICATION", {}).get("verified", 0),
            },
            "stage_results": results,
            "message": (
                f"Pipeline completed: {sum(1 for r in results.values() if r.get('success'))}/{len(stages)} stages successful"
                + (f" ({len(errors)} errors)" if errors else "")
            ),
        }
    except Exception as e:
        logger.error(f"Full cycle failed: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "message": "Full pipeline cycle failed",
        }


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server.run()
