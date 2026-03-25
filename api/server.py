"""
ACOE -- FastAPI Layer v2
Read-only endpoints + metrics, simulation, prediction, health.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ACOE -- Autonomous Cost Optimization Engine",
    version="2.0.0",
    description="Self-driving financial optimization engine API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_orchestrator = None


def set_orchestrator(orch):
    global _orchestrator
    _orchestrator = orch


def _get_orch():
    if _orchestrator is None:
        raise HTTPException(503, "Orchestrator not initialized")
    return _orchestrator


# ── Existing Endpoints ───────────────────────────────────────────────────────

@app.get("/status", tags=["System"])
def system_status():
    orch = _get_orch()
    base = orch.get_status()
    # Add health check if process manager is available
    if hasattr(app.state, "cb_manager"):
        base["circuit_breakers"] = app.state.cb_manager.get_all_status()
    if hasattr(app.state, "safety"):
        base["safety_constraints"] = app.state.safety.get_constraints_summary()
    return base


@app.get("/health", tags=["System"])
def health_check():
    orch = _get_orch()
    return {
        "status": "healthy",
        "cycle_count": orch._cycle_count,
        "cumulative_savings_inr": orch._cumulative_savings,
    }


@app.get("/ingest", tags=["Pipeline"])
def get_ingested_data():
    orch = _get_orch()
    data = orch.latest_data
    if not data:
        return {"message": "No data ingested yet"}
    return {
        "procurement": len(data.get("procurement", [])),
        "saas": len(data.get("saas", [])),
        "cloud": len(data.get("cloud", [])),
        "sla": len(data.get("sla", [])),
        "total_records": sum(len(v) for v in data.values()),
    }


@app.get("/analyze", tags=["Pipeline"])
def get_analysis():
    orch = _get_orch()
    issues = orch.latest_issues
    if not issues:
        return {"message": "No analysis data yet", "issues": []}
    return {
        "total_issues": len(issues),
        "issues": [
            {
                "id": i.issue_id,
                "category": i.category.value,
                "severity": i.severity.value,
                "title": i.title,
                "potential_savings_inr": i.potential_savings_inr,
            }
            for i in issues
        ],
    }


@app.get("/act", tags=["Pipeline"])
def get_actions():
    orch = _get_orch()
    actions = orch.latest_actions
    executions = orch.latest_executions
    return {
        "total_actions": len(actions),
        "actions": [
            {
                "id": a.action_id,
                "type": a.action_type.value,
                "title": a.title,
                "savings_inr": a.estimated_savings_inr,
                "confidence": a.confidence_score,
                "risk": a.risk_score,
                "roi": a.roi_estimate,
                "status": a.status.value,
            }
            for a in actions
        ],
        "executions": [
            {
                "id": e.execution_id,
                "action_id": e.action_id,
                "status": e.status.value,
                "verified": e.verified,
            }
            for e in executions
        ],
    }


@app.get("/report", tags=["Pipeline"])
def get_report():
    orch = _get_orch()
    report = orch.latest_report
    if not report:
        return {"message": "No report generated yet"}
    return {
        "report_id": report.report_id,
        "realized_savings_inr": report.realized_savings_inr,
        "projected_annual_savings_inr": report.projected_annual_savings_inr,
        "avoided_penalties_inr": report.avoided_penalties_inr,
        "total_impact_inr": report.total_impact_inr,
        "summary": report.summary,
        "cumulative_savings_inr": orch._cumulative_savings,
    }


# ── Metrics Endpoint ─────────────────────────────────────────────────────────

@app.get("/metrics", tags=["Analytics"])
def get_metrics():
    if not hasattr(app.state, "metrics") or app.state.metrics is None:
        return {"message": "Metrics not available"}
    return {
        "current_cycle": app.state.metrics.get_current(),
        "cumulative": app.state.metrics.get_cumulative(),
        "history": app.state.metrics.get_history()[-10:],
    }


# ── Simulation Endpoints ────────────────────────────────────────────────────

@app.get("/simulate", tags=["Analytics"])
def get_simulation(scenario: str = Query("balanced", enum=["aggressive", "conservative", "balanced"])):
    orch = _get_orch()
    if not hasattr(app.state, "simulation") or app.state.simulation is None:
        return {"message": "Simulation engine not available"}
    actions = orch.latest_actions
    issues = orch.latest_issues
    if not actions:
        return {"message": "No actions available for simulation"}
    return app.state.simulation.what_if(scenario, actions, issues)


@app.get("/simulate/compare", tags=["Analytics"])
def compare_strategies():
    orch = _get_orch()
    if not hasattr(app.state, "simulation") or app.state.simulation is None:
        return {"message": "Simulation engine not available"}
    all_scenarios = {}
    for scenario in ["aggressive", "conservative", "balanced"]:
        all_scenarios[scenario] = app.state.simulation.what_if(
            scenario, orch.latest_actions, orch.latest_issues
        )
    return all_scenarios


# ── Prediction Endpoints ────────────────────────────────────────────────────

@app.get("/predict", tags=["Analytics"])
def get_predictions():
    orch = _get_orch()
    return orch.latest_predictions or {"message": "No predictions yet"}


@app.get("/predict/sla-risks", tags=["Analytics"])
def get_sla_risk_predictions():
    orch = _get_orch()
    preds = orch.latest_predictions
    if preds and "sla_risks" in preds:
        return {"sla_risks": preds["sla_risks"]}
    return {"message": "No SLA risk predictions yet"}


@app.get("/predict/cost-leaks", tags=["Analytics"])
def get_cost_leak_predictions():
    orch = _get_orch()
    preds = orch.latest_predictions
    if preds and "cost_leaks" in preds:
        return {"cost_leaks": preds["cost_leaks"]}
    return {"message": "No cost leak predictions yet"}


# ── Dead Letter Queue ────────────────────────────────────────────────────────

@app.get("/dlq", tags=["System"])
def get_dead_letter_queue():
    if not hasattr(app.state, "state_db") or app.state.state_db is None:
        return {"message": "State DB not available"}
    return {"items": app.state.state_db.get_dlq_items()}


# ── Circuit Breakers ─────────────────────────────────────────────────────────

@app.get("/circuit-breakers", tags=["System"])
def get_circuit_breakers():
    if not hasattr(app.state, "cb_manager") or app.state.cb_manager is None:
        return {"message": "Circuit breakers not available"}
    return {"breakers": app.state.cb_manager.get_all_status()}


# ── Configuration ────────────────────────────────────────────────────────────

@app.get("/config", tags=["System"])
def get_config_endpoint():
    from config import get_config
    return get_config().to_dict()


# ── History ──────────────────────────────────────────────────────────────────

@app.get("/history/issues", tags=["History"])
def get_issues_history(limit: int = Query(50, ge=1, le=500)):
    if not hasattr(app.state, "state_db") or app.state.state_db is None:
        return {"message": "State DB not available"}
    return {"issues": app.state.state_db.get_issues_history(limit)}


@app.get("/history/savings", tags=["History"])
def get_savings_history(limit: int = Query(20, ge=1, le=100)):
    if not hasattr(app.state, "state_db") or app.state.state_db is None:
        return {"message": "State DB not available"}
    return {"cycles": app.state.state_db.get_savings_history(limit)}
