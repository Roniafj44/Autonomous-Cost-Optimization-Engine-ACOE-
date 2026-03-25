"""
ACOE -- Streamlit Dashboard v2
Read-only observability with metrics, simulation, predictions.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

import requests
import streamlit as st

API_URL = os.environ.get("ACOE_API_URL", "http://localhost:8000")


def api_get(endpoint: str, params: dict = None) -> dict:
    try:
        r = requests.get(f"{API_URL}{endpoint}", params=params, timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ACOE Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0a0a0a; color: #e0e0e0; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
    }
    .metric-value { font-size: 28px; font-weight: 700; color: #00d4aa; }
    .metric-label { font-size: 13px; color: #888; text-transform: uppercase; }
    .status-ok { color: #00d4aa; }
    .status-warn { color: #ffa500; }
    .status-err { color: #ff4444; }
    h1, h2, h3 { color: #e0e0e0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("ACOE v2")
    st.caption("Autonomous Cost Optimization Engine")
    st.divider()
    refresh = st.slider("Auto-refresh (sec)", 10, 120, 30)
    st.divider()

    status = api_get("/status")
    if "error" not in status:
        st.metric("Cycles", status.get("cycle_count", 0))
        savings = status.get("cumulative_savings_inr", 0)
        st.metric("Total Savings", f"INR {savings:,.0f}")
    else:
        st.error("API unavailable")

    st.divider()
    st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview", "Issues", "Actions", "Financial Impact",
    "Metrics", "Simulation", "Predictions",
])

# ── Tab 1: Overview ──────────────────────────────────────────────────────────

with tab1:
    st.header("System Overview")

    col1, col2, col3, col4 = st.columns(4)
    health = api_get("/health")
    if "error" not in health:
        col1.metric("Status", "HEALTHY" if health.get("status") == "healthy" else "DEGRADED")
        col2.metric("Cycles", health.get("cycle_count", 0))
        col3.metric("Savings", f"INR {health.get('cumulative_savings_inr', 0):,.0f}")

    ingest = api_get("/ingest")
    if "error" not in ingest and "total_records" in ingest:
        col4.metric("Records", ingest.get("total_records", 0))

    st.divider()

    # Circuit breakers
    cb_data = api_get("/circuit-breakers")
    if "breakers" in cb_data:
        st.subheader("Circuit Breakers")
        cols = st.columns(len(cb_data["breakers"]))
        for i, cb in enumerate(cb_data["breakers"]):
            state = cb.get("state", "unknown")
            color = "green" if state == "closed" else ("orange" if state == "half_open" else "red")
            cols[i].markdown(
                f"**{cb['name']}**<br>"
                f"<span style='color:{color}'>{state.upper()}</span><br>"
                f"Failures: {cb.get('failures', 0)}/{cb.get('threshold', 3)}",
                unsafe_allow_html=True,
            )

    # Config
    with st.expander("Configuration"):
        cfg = api_get("/config")
        if "error" not in cfg:
            st.json(cfg)

# ── Tab 2: Issues ────────────────────────────────────────────────────────────

with tab2:
    st.header("Detected Inefficiencies")
    analysis = api_get("/analyze")
    if "issues" in analysis and analysis["issues"]:
        st.metric("Total Issues", analysis["total_issues"])
        for issue in analysis["issues"]:
            sev = issue.get("severity", "low")
            color = {"critical": "red", "high": "orange", "medium": "yellow", "low": "green"}.get(sev, "gray")
            st.markdown(
                f"**[{sev.upper()}]** {issue['title']} — "
                f"*{issue['category']}* — INR {issue.get('potential_savings_inr', 0):,.0f}",
            )
    else:
        st.info("No issues detected yet. Waiting for first cycle...")

# ── Tab 3: Actions ───────────────────────────────────────────────────────────

with tab3:
    st.header("Executed Actions")
    act_data = api_get("/act")
    if "actions" in act_data and act_data["actions"]:
        st.metric("Total Actions", act_data["total_actions"])
        for action in act_data["actions"]:
            st.markdown(
                f"**{action['title']}**  \n"
                f"Type: `{action['type']}` | "
                f"Savings: INR {action.get('savings_inr', 0):,.0f} | "
                f"Confidence: {action.get('confidence', 0):.0%} | "
                f"Risk: {action.get('risk', 0):.0%} | "
                f"ROI: {action.get('roi', 0):.1f}x"
            )

        # Execution status
        st.divider()
        st.subheader("Execution Log")
        for ex in act_data.get("executions", []):
            icon = "OK" if ex.get("verified") else "PENDING"
            st.text(f"  [{icon}] {ex['action_id']} -> {ex['status']}")
    else:
        st.info("No actions executed yet.")

# ── Tab 4: Financial Impact ──────────────────────────────────────────────────

with tab4:
    st.header("Financial Impact Report")
    report = api_get("/report")
    if "report_id" in report:
        col1, col2, col3 = st.columns(3)
        col1.metric("Realized Savings", f"INR {report.get('realized_savings_inr', 0):,.0f}")
        col2.metric("Projected Annual", f"INR {report.get('projected_annual_savings_inr', 0):,.0f}")
        col3.metric("Avoided Penalties", f"INR {report.get('avoided_penalties_inr', 0):,.0f}")

        st.divider()
        st.metric("TOTAL IMPACT", f"INR {report.get('total_impact_inr', 0):,.0f}")
        st.metric("Cumulative Savings", f"INR {report.get('cumulative_savings_inr', 0):,.0f}")
        st.text(report.get("summary", ""))
    else:
        st.info("No impact report yet.")

# ── Tab 5: Metrics ───────────────────────────────────────────────────────────

with tab5:
    st.header("System Metrics")
    metrics = api_get("/metrics")
    if "current_cycle" in metrics and metrics["current_cycle"]:
        current = metrics["current_cycle"]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Success Rate", f"{current.get('success_rate', 0):.0f}%")
        col2.metric("Avg ROI", f"{current.get('avg_roi', 0):.1f}x")
        col3.metric("Avg Risk", f"{current.get('avg_risk', 0):.1%}")
        col4.metric("SLA Risks Avoided", current.get("sla_risks_avoided", 0))

        st.divider()
        cumul = metrics.get("cumulative", {})
        if cumul and cumul.get("total_cycles"):
            st.subheader("Cumulative")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Cycles", cumul.get("total_cycles", 0))
            c2.metric("Total Savings", f"INR {cumul.get('total_savings_inr', 0):,.0f}")
            c3.metric("Actions Executed", cumul.get("total_actions_executed", 0))
            c4.metric("Overall Success", f"{cumul.get('overall_success_rate', 0):.0f}%")
    else:
        st.info("Metrics will appear after first cycle.")

# ── Tab 6: Simulation ───────────────────────────────────────────────────────

with tab6:
    st.header("What-If Simulation")
    scenario = st.selectbox("Scenario", ["balanced", "aggressive", "conservative"])
    sim = api_get("/simulate", {"scenario": scenario})
    if "aggregate" in sim:
        agg = sim["aggregate"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Strategies Evaluated", sim.get("filtered_count", 0))
        col2.metric("Total Base Savings", f"INR {agg.get('total_base_savings_inr', 0):,.0f}")
        col3.metric("Risk-Adjusted Savings", f"INR {agg.get('total_adjusted_savings_inr', 0):,.0f}")

        st.divider()
        if sim.get("recommendation"):
            st.success(f"Top Recommendation: **{sim['recommendation']}**")

        st.subheader("Strategy Comparison")
        for s in sim.get("strategies", [])[:10]:
            st.markdown(
                f"**{s['title']}** — "
                f"Base: INR {s['base_savings_inr']:,.0f} | "
                f"Adjusted: INR {s['confidence_adjusted_savings_inr']:,.0f} | "
                f"Risk: {s['risk_score']:.0%}"
            )
    else:
        st.info("Run a cycle first to enable simulation.")

# ── Tab 7: Predictions ──────────────────────────────────────────────────────

with tab7:
    st.header("Cost Leak Predictions")
    preds = api_get("/predict")

    if "cost_leaks" in preds and preds["cost_leaks"]:
        st.subheader("Predicted Cost Leaks (3-Month)")
        for leak in preds["cost_leaks"][:10]:
            sev_color = "red" if leak.get("severity") == "high" else "orange"
            st.markdown(
                f"**[{leak.get('severity', '').upper()}]** {leak['name']} "
                f"({leak['entity_type']}) — "
                f"Utilization: {leak.get('current_utilization', 0):.0%} | "
                f"Monthly Waste: INR {leak.get('monthly_waste_inr', 0):,.0f} | "
                f"3-Mo Projected: INR {leak.get('projected_3mo_waste_inr', 0):,.0f} | "
                f"Rec: **{leak.get('recommendation', 'N/A')}**"
            )

    if "sla_risks" in preds and preds["sla_risks"]:
        st.divider()
        st.subheader("SLA Risk Predictions")
        for risk in preds["sla_risks"][:10]:
            st.markdown(
                f"**[{risk.get('risk_level', '')}]** {risk['service']} — "
                f"{risk['metric']} | "
                f"Compliance: {risk.get('current_compliance', 0):.2%} | "
                f"Hours to breach: {risk.get('hours_to_breach', 'N/A')} | "
                f"Penalty at risk: INR {risk.get('penalty_at_risk_inr', 0):,.0f}"
            )

    if "savings_trend" in preds:
        st.divider()
        st.subheader("Savings Trend Forecast")
        trend = preds["savings_trend"]
        if trend.get("status") == "ok":
            st.metric("Trend", trend.get("trend", "unknown").upper())
            for pred in trend.get("predictions", []):
                st.text(f"  {pred['period']}: INR {pred['predicted_savings_inr']:,.0f}")
        else:
            st.info(trend.get("message", "Insufficient data for prediction"))

    if not any(k in preds for k in ("cost_leaks", "sla_risks", "savings_trend")):
        st.info("Predictions will appear after first cycle.")

# ── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(refresh)
st.rerun()
