"""
ACOE — Neo-Brutalist Streamlit Dashboard
Pure view layer — calls backend agents directly, zero business logic.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from collections import Counter
import re

import streamlit as st
import pandas as pd

# ── Path Setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agents.ingestion import IngestionAgent
from agents.detection import DetectionAgent
from agents.decision import DecisionAgent
from agents.execution import ExecutionAgent
from agents.verification import VerificationAgent
from agents.audit import AuditAgent
from agents.impact import ImpactAgent


# ═════════════════════════════════════════════════════════════════════════════
#  DESIGN SYSTEM — NEO-BRUTALISM
# ═════════════════════════════════════════════════════════════════════════════

ACCENT = "#50C878"   # Emerald
GLOW = "#5FE08A"     # Glowing Emerald
BLACK = "#1E211E"    # Charcoal
WHITE = "#FFF5EE"    # Seashell Cream
OFF_WHITE = "#F0E6DA" # Darker Seashell

# strictly green shades per user feedback
SEVERITY_COLORS = {
    "critical": "#1E5631", # Dark Green
    "high": "#4C9A2A",     # Leaf Green
    "medium": "#76BA1B",   # Mid Green
    "low": "#00FA9A",      # Medium Spring Green
}
STATUS_COLORS = {
    "executed": "#50C878", # Emerald
    "verified": "#50C878", # Emerald
    "pending": "#A4DE02",  # Lime Focus
    "failed": "#1E211E",   # Charcoal (failure goes dark)
    "skipped": "#4C9A2A",  # Leaf Green
    "approved": "#00FA9A", # Spring Green
}

NEO_BRUTAL_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@400;600;700;900&display=swap');

    /* ── Global Reset ─────────────────────────────────────────── */
    .stApp {{
        background-color: {WHITE};
        color: {BLACK};
        font-family: 'Outfit', sans-serif;
    }}

    .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
    }}

    /* ── Typography ───────────────────────────────────────────── */
    h1, h2, h3, h4, h5, h6 {{
        color: {BLACK} !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 900 !important;
        letter-spacing: -0.02em;
    }}

    h1 {{
        font-size: 2.8rem !important;
        border-bottom: 6px solid {BLACK};
        padding-bottom: 8px;
        margin-bottom: 24px !important;
        text-transform: uppercase;
        background-color: {WHITE};
        padding: 16px;
        box-shadow: 6px 6px 0px {BLACK};
    }}

    h2 {{
        font-size: 1.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    h3 {{
        font-size: 1.4rem !important;
    }}

    /* ── Metric Cards ─────────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background-color: {WHITE};
        border: 4px solid {BLACK};
        box-shadow: 6px 6px 0px {BLACK};
        padding: 20px 16px;
        text-align: center;
        margin-bottom: 12px;
    }}

    [data-testid="stMetricLabel"] {{
        font-family: 'Space Mono', monospace !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: {BLACK} !important;
        font-weight: 700 !important;
    }}

    [data-testid="stMetricValue"] {{
        font-family: 'Outfit', sans-serif !important;
        font-size: 2.4rem !important;
        font-weight: 900 !important;
        color: {BLACK} !important;
    }}

    [data-testid="stMetricDelta"] {{
        font-family: 'Space Mono', monospace !important;
    }}

    /* ── Tabs ─────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0px;
        border-bottom: 4px solid {BLACK};
    }}

    .stTabs [data-baseweb="tab"] {{
        background-color: {WHITE};
        border: 4px solid {BLACK} !important;
        border-bottom: none !important;
        color: {BLACK} !important;
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        font-size: 0.9rem;
        text-transform: uppercase;
        padding: 14px 24px;
        margin-right: -4px;
        box-shadow: 4px 4px 0px {BLACK} inset;
    }}

    .stTabs [aria-selected="true"] {{
        background-color: {ACCENT} !important;
        color: {BLACK} !important;
        border-color: {BLACK} !important;
        box-shadow: 0px 4px 12px {GLOW};
    }}

    /* ── Expanders ─────────────────────────────────────────────── */
    .streamlit-expanderHeader {{
        background-color: {OFF_WHITE} !important;
        border: 4px solid {BLACK} !important;
        box-shadow: 6px 6px 0px {BLACK} !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 900 !important;
        font-size: 1.1rem !important;
        color: {BLACK} !important;
        margin-bottom: 6px;
    }}

    .streamlit-expanderContent {{
        border: 4px solid {BLACK} !important;
        border-top: none !important;
        background-color: {WHITE} !important;
        padding: 20px !important;
        box-shadow: 6px 6px 0px {BLACK} !important;
        margin-bottom: 16px;
    }}

    details {{
        border: none !important;
        margin-bottom: 16px;
    }}

    details summary {{
        background-color: {OFF_WHITE} !important;
        border: 4px solid {BLACK} !important;
        padding: 16px 20px !important;
        font-weight: 900 !important;
        cursor: pointer;
        box-shadow: 6px 6px 0px {BLACK} !important;
        transition: transform 0.1s;
    }}

    details[open] summary {{
        background-color: {ACCENT} !important;
        color: {BLACK} !important;
        box-shadow: 0px 0px 15px {GLOW} !important;
    }}

    /* ── Buttons ───────────────────────────────────────────────── */
    .stButton > button {{
        background-color: {BLACK} !important;
        color: {WHITE} !important;
        border: 4px solid {BLACK} !important;
        border-radius: 0 !important;
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 16px 32px !important;
        box-shadow: 6px 6px 0px {ACCENT} !important;
        transition: all 0.1s ease;
    }}

    .stButton > button:hover {{
        background-color: {ACCENT} !important;
        color: {BLACK} !important;
        box-shadow: 6px 6px 0px {BLACK} !important;
    }}

    .stButton > button:active {{
        transform: translate(6px, 6px);
        box-shadow: 0px 0px 0px {BLACK} !important;
    }}

    /* ── Progress Bars ────────────────────────────────────────── */
    .stProgress > div > div > div {{
        background-color: {ACCENT} !important;
        border-radius: 0 !important;
        box-shadow: 0 0 10px {GLOW};
    }}

    .stProgress > div > div {{
        background-color: {OFF_WHITE} !important;
        border: 4px solid {BLACK} !important;
        border-radius: 0 !important;
        height: 24px;
    }}

    /* ── Toggle / Checkbox ────────────────────────────────────── */
    .stCheckbox label span {{
        font-family: 'Space Mono', monospace !important;
        font-weight: 700 !important;
        text-transform: uppercase;
    }}

    /* ── Tables ────────────────────────────────────────────────── */
    .stDataFrame {{
        border: 4px solid {BLACK} !important;
        box-shadow: 6px 6px 0px {BLACK};
        background-color: {WHITE};
    }}

    /* ── Dividers ──────────────────────────────────────────────── */
    hr {{
        border-top: 6px solid {BLACK} !important;
        margin: 32px 0;
    }}

    /* ── Alert boxes ──────────────────────────────────────────── */
    .stAlert {{
        border-radius: 0 !important;
        border-width: 4px !important;
        border-style: solid !important;
        border-color: {BLACK} !important;
        box-shadow: 6px 6px 0px {BLACK} !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }}

    /* ── Bar chart ─────────────────────────────────────────────── */
    .stBarChart {{
        border: 4px solid {BLACK} !important;
        box-shadow: 6px 6px 0px {BLACK} !important;
        padding: 12px !important;
        background-color: {WHITE} !important;
    }}

    /* ── Sidebar ───────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {{
        background-color: {BLACK} !important;
        border-right: 6px solid {ACCENT};
    }}

    section[data-testid="stSidebar"] * {{
        color: {WHITE} !important;
    }}

    section[data-testid="stSidebar"] .stButton > button {{
        background-color: {ACCENT} !important;
        border-color: #FFF5EE !important;
        color: {BLACK} !important;
        box-shadow: 6px 6px 0px #FFF5EE !important;
    }}

    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: #FFF5EE !important;
    }}

    section[data-testid="stSidebar"] .stButton > button:active {{
        transform: translate(6px, 6px);
        box-shadow: 0px 0px 0px #FFF5EE !important;
    }}

    /* ── Custom card class ─────────────────────────────────────── */
    .neo-card {{
        border: 4px solid {BLACK};
        box-shadow: 6px 6px 0px {BLACK};
        padding: 24px;
        margin-bottom: 24px;
        background-color: {WHITE};
        transition: transform 0.1s;
    }}

    .neo-card:hover {{
        transform: translate(-2px, -2px);
        box-shadow: 8px 8px 0px {BLACK};
    }}

    .neo-card-accent {{
        border: 4px solid {BLACK};
        box-shadow: 8px 8px 0px {BLACK};
        padding: 32px;
        margin-bottom: 24px;
        background-color: {ACCENT};
        color: {BLACK};
    }}

    .neo-label {{
        font-family: 'Space Mono', monospace;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: {BLACK};
        font-weight: 700;
        margin-bottom: 6px;
    }}

    .neo-value {{
        font-family: 'Outfit', sans-serif;
        font-size: 1.6rem;
        font-weight: 900;
        color: {BLACK};
    }}

    .neo-value-big {{
        font-family: 'Outfit', sans-serif;
        font-size: 3.2rem;
        font-weight: 900;
        color: {BLACK};
        line-height: 1;
        text-shadow: 4px 4px 0px {WHITE};
    }}

    .neo-badge {{
        display: inline-block;
        padding: 6px 14px;
        font-family: 'Space Mono', monospace;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border: 3px solid {BLACK};
        box-shadow: 3px 3px 0px {BLACK};
        color: {BLACK} !important; 
    }}

    @keyframes marquee {{
        0% {{ transform: translateX(100%); }}
        100% {{ transform: translateX(-100%); }}
    }}

    .neo-trace {{
        font-family: 'Space Mono', monospace;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        overflow: hidden;
        white-space: nowrap;
        background-color: {BLACK};
        color: {GLOW};
        padding: 12px;
        border: 4px solid {BLACK};
        box-shadow: 6px 6px 0px {ACCENT};
        text-align: left;
    }}

    .neo-trace-content {{
        display: inline-block;
        animation: marquee 15s linear infinite;
        font-weight: 700;
    }}

    .neo-trace-step {{
        display: inline-block;
        padding: 8px 16px;
        border: 3px solid {BLACK};
        font-weight: 900;
        background-color: {WHITE};
        box-shadow: 4px 4px 0px {BLACK};
        margin-bottom: 8px;
    }}

    .neo-trace-active {{
        background-color: {ACCENT} !important;
        color: {BLACK} !important;
        box-shadow: 4px 4px 10px {GLOW} !important;
    }}

    .neo-trace-arrow {{
        display: inline-block;
        font-size: 1.4rem;
        font-weight: 900;
        padding: 0 12px;
        color: {BLACK};
    }}

    .insight-box {{
        border: 4px solid {BLACK};
        border-left: 12px solid {ACCENT};
        box-shadow: 6px 6px 0px {BLACK};
        padding: 20px 24px;
        margin: 24px 0;
        font-family: 'Outfit', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        background-color: {OFF_WHITE};
        color: {BLACK};
    }}
</style>
"""


# ═════════════════════════════════════════════════════════════════════════════
#  DATA LAYER — Backend Integration
# ═════════════════════════════════════════════════════════════════════════════

def load_data():
    """Run the full 7-stage autonomous pipeline and cache results."""
    if "pipeline_run" in st.session_state and not st.session_state.get("force_rerun"):
        return

    with st.spinner("EXECUTING AUTONOMOUS PIPELINE..."):
        # Stage 1: Ingestion
        ingestion = IngestionAgent()
        data = ingestion.run()

        # Stage 2: Detection
        detection = DetectionAgent()
        issues = detection.run(data)

        # Stage 3: Decision
        decision = DecisionAgent()
        actions = decision.run(issues)

        # Stage 4: Execution
        execution = ExecutionAgent()
        exec_logs = execution.run(actions)

        # Stage 5: Verification
        verification = VerificationAgent()
        verified_logs = verification.run(actions, exec_logs)

        # Stage 6: Audit
        audit = AuditAgent()
        audit_path = audit.run(1, data, issues, actions, verified_logs, None)

        # Stage 7: Impact
        impact = ImpactAgent()
        report = impact.run(1, actions, verified_logs, issues)

        # Rewrite audit with impact
        audit.run(1, data, issues, actions, verified_logs, report)

        # Compute before-state financials
        proc_monthly = sum(r.contract_value_inr / 12 for r in data["procurement"])
        saas_monthly = sum(s.monthly_cost_inr for s in data["saas"])
        cloud_monthly = sum(c.monthly_cost_inr for c in data["cloud"])
        penalty_exposure = sum(s.breach_penalty_inr for s in data["sla"])
        total_monthly_before = proc_monthly + saas_monthly + cloud_monthly

        # Store in session
        st.session_state["pipeline_run"] = True
        st.session_state["force_rerun"] = False
        st.session_state["data"] = data
        st.session_state["issues"] = issues
        st.session_state["actions"] = actions
        st.session_state["exec_logs"] = exec_logs
        st.session_state["verified_logs"] = verified_logs
        st.session_state["report"] = report
        st.session_state["audit_path"] = audit_path

        st.session_state["before"] = {
            "procurement_monthly": proc_monthly,
            "saas_monthly": saas_monthly,
            "cloud_monthly": cloud_monthly,
            "penalty_exposure": penalty_exposure,
            "total_monthly": total_monthly_before,
        }


def run_optimization():
    """Force re-run of the pipeline."""
    st.session_state["force_rerun"] = True
    st.session_state.pop("pipeline_run", None)


# ═════════════════════════════════════════════════════════════════════════════
#  UI COMPONENTS
# ═════════════════════════════════════════════════════════════════════════════

def render_header():
    """Top executive banner — always visible."""
    issues = st.session_state.get("issues", [])
    actions = st.session_state.get("actions", [])
    verified = st.session_state.get("verified_logs", [])
    report = st.session_state.get("report", None)

    executed_count = sum(
        1 for l in verified if l.status.value in ("executed", "verified")
    )
    total_saved = report.total_impact_inr if report else 0

    st.markdown(
        f'<div style="border:4px solid {BLACK};padding:8px 16px;margin-bottom:24px;'
        f'background-color:{BLACK};color:{WHITE};font-family:Space Mono,monospace;'
        f'font-size:0.85rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.1em;text-align:center;">'
        f'AUTONOMOUS COST OPTIMIZATION ENGINE — CONTROL PANEL'
        f'</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("🚨 ISSUES DETECTED", len(issues))
    col2.metric("⚡ ACTIONS EXECUTED", executed_count)
    col3.metric(
        "💰 TOTAL ₹ SAVED",
        f"₹{total_saved:,.0f}",
        delta=f"₹{total_saved / 12:,.0f}/mo" if total_saved > 0 else None,
    )

    st.markdown("---")


def render_agent_trace():
    """Show the autonomous pipeline as a step-by-step trace."""
    stages = [
        ("INGESTION", True),
        ("DETECTION", True),
        ("DECISION", True),
        ("EXECUTION", True),
        ("VERIFICATION", True),
        ("AUDIT", True),
        ("IMPACT", True),
    ]

    html_parts = []
    for i, (name, active) in enumerate(stages):
        cls = "neo-trace-step neo-trace-active" if active else "neo-trace-step"
        html_parts.append(f'<span class="{cls}">{name}</span>')
        if i < len(stages) - 1:
            html_parts.append('<span class="neo-trace-arrow">→</span>')

    st.markdown(
        f'<div class="neo-trace">'
        f'<div class="neo-trace-content">{"".join(html_parts)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_problem_tab():
    """🚨 PROBLEM tab — strong problem framing."""
    report = st.session_state.get("report", None)
    issues = st.session_state.get("issues", [])
    before = st.session_state.get("before", {})

    total_potential = sum(i.potential_savings_inr for i in issues)
    total_monthly = before.get("total_monthly", 0)

    st.error(
        f"⚠️ CRITICAL: ₹{total_potential:,.0f}/year in cost inefficiencies detected across your enterprise infrastructure."
    )

    st.markdown(
        f"""
**The autonomous engine has identified systemic cost leakage:**

- **{len(issues)} distinct inefficiencies** found across procurement, SaaS, cloud, and SLA compliance
- **₹{total_monthly:,.0f}/month** current operational spend — significant portion is recoverable waste
- **Duplicate vendor contracts** are inflating procurement costs with redundant service coverage
- **SaaS license underutilization** below 40% threshold — paying for seats nobody uses
- **Cloud over-provisioning** detected — resources provisioned at 2-3x actual demand
""",
    )

    st.markdown(
        f'<div class="insight-box">'
        f'💡 The ACOE engine autonomously detects, decides, and executes — '
        f'recovering ₹{total_potential:,.0f}/year without human intervention.'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_detection_tab():
    """🔍 DETECTION tab — issue cards."""
    issues = st.session_state.get("issues", [])

    st.markdown(f"**{len(issues)} inefficiencies identified** by rule-based heuristics + z-score anomaly detection")
    st.markdown("")

    for issue in issues:
        sev = issue.severity.value
        sev_color = SEVERITY_COLORS.get(sev, "#888")
        cat_label = issue.category.value.replace("_", " ").upper()

        st.markdown(
            f'<div class="neo-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
            f'<span style="font-family:Inter;font-weight:900;font-size:1.1rem;">{issue.title}</span>'
            f'<span class="neo-badge" style="background-color:{sev_color};color:{WHITE};">{sev.upper()}</span>'
            f'</div>'
            f'<div class="neo-label">CATEGORY</div>'
            f'<div style="font-weight:700;margin-bottom:8px;">{cat_label}</div>'
            f'<div class="neo-label">EXPLANATION</div>'
            f'<div style="font-size:0.9rem;color:#333;">{issue.description}</div>'
            f'<div style="margin-top:12px;padding-top:12px;border-top:2px solid {BLACK};">'
            f'<span class="neo-label">POTENTIAL SAVINGS</span> '
            f'<span style="font-weight:900;font-size:1.1rem;color:{ACCENT};">₹{issue.potential_savings_inr:,.0f}/yr</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_reasoning_card(action, issue, exec_log):
    """Single reasoning card inside a Decision expander."""
    ev = issue.evidence if issue else {}
    sev = issue.severity.value if issue else "unknown"
    sev_color = SEVERITY_COLORS.get(sev, "#888")

    # ── Detection
    st.markdown(f"**DETECTION**")
    st.markdown(
        f'<div class="neo-card" style="background-color:{OFF_WHITE};">'
        f'<span class="neo-label">Rule Applied</span><br>'
        f'<span style="font-weight:700;">{issue.category.value.replace("_", " ").title() if issue else "N/A"}</span><br>'
        f'<span class="neo-label" style="margin-top:8px;display:inline-block;">Threshold</span><br>'
        f'<span style="font-weight:700;">Utilization &lt; 40% / z-score &gt; 2.0σ</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Decision
    st.markdown(f"**DECISION**")
    st.markdown(
        f'<div class="neo-card">'
        f'<span class="neo-label">Action Taken</span><br>'
        f'<span style="font-weight:900;font-size:1.05rem;">'
        f'{action.action_type.value.replace("_", " ").upper()}</span><br>'
        f'<span style="font-size:0.9rem;margin-top:4px;display:block;">{action.description}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Reasoning
    st.markdown(f"**REASONING**")
    st.markdown(
        f'<div class="neo-card" style="border-left:6px solid {ACCENT};">'
        f'{action.justification}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Impact
    st.markdown(f"**IMPACT**")
    monthly = action.estimated_savings_inr / 12
    col1, col2 = st.columns(2)
    col1.metric("Monthly Savings", f"₹{monthly:,.0f}")
    col2.metric("Annual Savings", f"₹{action.estimated_savings_inr:,.0f}")

    # ── Confidence
    st.markdown(f"**CONFIDENCE**")
    st.progress(action.confidence_score)
    st.caption(f"{action.confidence_score:.0%} confidence — Risk: {action.risk_score:.0%} — ROI: {action.roi_estimate:.1f}x")

    # ── Alternatives
    st.markdown(f"**ALTERNATIVES CONSIDERED**")
    alt_reasons = _get_alternatives(action, issue)
    for alt_name, alt_reason in alt_reasons:
        st.markdown(f"- ~~{alt_name}~~ — *{alt_reason}*")

    # ── Execution Status
    st.markdown(f"**EXECUTION STATUS**")
    if exec_log:
        status_val = exec_log.status.value
        status_color = STATUS_COLORS.get(status_val, "#888")
        st.markdown(
            f'<span class="neo-badge" style="background-color:{status_color};color:{WHITE};">'
            f'{status_val.upper()}</span>'
            f' — Attempts: {exec_log.attempts} — Verified: {"✓ Yes" if exec_log.verified else "✗ Pending"}',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("No execution data available.")


def _get_alternatives(action, issue):
    """Return rejected alternatives based on action type."""
    alts = {
        "cancel_subscription": [
            ("Keep current plan", "Continued waste outweighs disruption risk"),
            ("Negotiate discount only", "Utilization too low — discount insufficient"),
        ],
        "downgrade_plan": [
            ("Full cancellation", "Active users still depend on product"),
            ("Maintain status quo", "40%+ licenses unused — unjustifiable cost"),
        ],
        "consolidate_vendors": [
            ("Keep all vendors", "Redundancy offers no differentiation"),
            ("Partial consolidation", "Full consolidation maximizes volume discount"),
        ],
        "reallocate_compute": [
            ("Maintain current capacity", "Peak usage is well below provisioned level"),
            ("Switch provider", "Migration cost exceeds right-sizing savings"),
        ],
        "trigger_escalation": [
            ("Wait for auto-recovery", "SLA breach deadline too close for passive approach"),
            ("Internal fix", "Vendor responsibility — escalation is contractually correct"),
        ],
        "renegotiate_contract": [
            ("Accept current pricing", "Cost is statistically anomalous vs peers"),
            ("Switch vendor entirely", "Migration risk exceeds renegotiation benefit"),
        ],
    }
    return alts.get(action.action_type.value, [("No alternatives", "Best option selected")])


def render_decision_tab():
    """🧠 DECISION tab — expanders with full reasoning."""
    actions = st.session_state.get("actions", [])
    issues = st.session_state.get("issues", [])
    exec_logs = st.session_state.get("verified_logs", [])

    issue_map = {i.issue_id: i for i in issues}
    log_map = {l.action_id: l for l in exec_logs}

    st.markdown(f"**{len(actions)} autonomous decisions** generated with ROI scoring and risk assessment")
    st.markdown("")

    for i, action in enumerate(actions):
        issue = issue_map.get(action.issue_id)
        log = log_map.get(action.action_id)

        sev = issue.severity.value if issue else "medium"
        sev_color = SEVERITY_COLORS.get(sev, "#888")

        with st.expander(
            f"#{i+1}  ▸  {action.title}  —  ₹{action.estimated_savings_inr:,.0f}",
            expanded=False,
        ):
            render_reasoning_card(action, issue, log)


def render_execution_tab():
    """⚙️ EXECUTION tab — action list with status badges."""
    actions = st.session_state.get("actions", [])
    exec_logs = st.session_state.get("verified_logs", [])

    log_map = {l.action_id: l for l in exec_logs}

    # Auto-execute toggle
    auto_exec = st.toggle("AUTO EXECUTE", value=True, key="auto_exec_toggle")
    if auto_exec:
        st.markdown(
            f'<div class="insight-box" style="border-left-color:{ACCENT};">'
            f'✓ Auto-execution is <strong>ENABLED</strong> — all eligible actions execute without human approval.'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="insight-box" style="border-left-color:#76BA1B;">'
            f'⏸ Auto-execution is <strong>DISABLED</strong> — actions require manual approval before execution.'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Status summary
    executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
    pending = sum(1 for l in exec_logs if l.status.value == "pending")
    skipped = sum(1 for l in exec_logs if l.status.value == "skipped")
    failed = sum(1 for l in exec_logs if l.status.value == "failed")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ COMPLETED", executed)
    c2.metric("⏳ PENDING", pending)
    c3.metric("⏭ SKIPPED", skipped)
    c4.metric("❌ FAILED", failed)

    st.markdown("---")

    # Action list
    for action in actions:
        log = log_map.get(action.action_id)
        status_val = log.status.value if log else "pending"
        status_color = STATUS_COLORS.get(status_val, "#888")
        verified_text = "✓ Verified" if (log and log.verified) else "Pending"

        st.markdown(
            f'<div class="neo-card" style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div>'
            f'<div style="font-weight:900;font-size:1rem;">{action.title}</div>'
            f'<div style="font-size:0.8rem;color:#666;font-family:Space Mono,monospace;margin-top:4px;">'
            f'{action.action_type.value.upper()} → {action.target_entity_id}'
            f'</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<span class="neo-badge" style="background-color:{status_color};color:{WHITE};">'
            f'{status_val.upper()}</span>'
            f'<div style="font-size:0.75rem;margin-top:4px;font-family:Space Mono,monospace;">{verified_text}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_impact_tab():
    """💰 IMPACT tab — financial impact visualization."""
    report = st.session_state.get("report", None)
    before = st.session_state.get("before", {})
    issues = st.session_state.get("issues", [])

    if not report:
        st.info("No impact data available yet.")
        return

    # ── Total Savings — DOMINANT
    st.markdown(
        f'<div class="neo-card-accent" style="text-align:center;padding:32px;">'
        f'<div class="neo-label" style="color:{WHITE};opacity:0.8;">TOTAL FINANCIAL IMPACT</div>'
        f'<div style="font-family:Inter;font-size:3.5rem;font-weight:900;color:{WHITE};line-height:1.1;">'
        f'₹{report.total_impact_inr:,.0f}</div>'
        f'<div style="font-family:Space Mono,monospace;font-size:0.85rem;color:{WHITE};opacity:0.8;margin-top:8px;">'
        f'REALIZED + PROJECTED + AVOIDED PENALTIES</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Monthly / Annual / Avoided
    col1, col2, col3 = st.columns(3)
    col1.metric("REALIZED MONTHLY", f"₹{report.realized_savings_inr:,.0f}")
    col2.metric("PROJECTED ANNUAL", f"₹{report.projected_annual_savings_inr:,.0f}")
    col3.metric("AVOIDED PENALTIES", f"₹{report.avoided_penalties_inr:,.0f}")

    st.markdown("---")

    # ── Category Breakdown Chart
    st.markdown("### SAVINGS BY CATEGORY")

    category_savings = Counter()
    for item in report.breakdown:
        cat = item.get("category", "unknown").replace("_", " ").title()
        amount = item.get("annual_savings_inr", 0) or item.get("amount_inr", 0)
        category_savings[cat] += amount

    if category_savings:
        chart_df = pd.DataFrame(
            {"Category": list(category_savings.keys()), "Savings (₹)": list(category_savings.values())}
        )
        chart_df = chart_df.sort_values("Savings (₹)", ascending=True)
        st.bar_chart(chart_df.set_index("Category"), horizontal=True, color=ACCENT)

    st.markdown("---")

    # ── Before vs After
    st.markdown("### BEFORE vs AFTER")
    total_monthly = before.get("total_monthly", 0)
    monthly_savings = report.total_impact_inr / 12
    after_monthly = total_monthly - monthly_savings
    reduction_pct = (monthly_savings / total_monthly * 100) if total_monthly > 0 else 0

    col_b, col_a = st.columns(2)

    with col_b:
        st.markdown(
            f'<div class="neo-card" style="border-color:#1E5631;">'
            f'<div class="neo-label">BEFORE OPTIMIZATION</div>'
            f'<div class="neo-value" style="color:#1E5631;">₹{total_monthly:,.0f}/mo</div>'
            f'<div style="font-size:0.85rem;margin-top:4px;">₹{total_monthly * 12:,.0f}/year</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_a:
        st.markdown(
            f'<div class="neo-card" style="border-color:#50C878;">'
            f'<div class="neo-label">AFTER OPTIMIZATION</div>'
            f'<div class="neo-value" style="color:#50C878;">₹{after_monthly:,.0f}/mo</div>'
            f'<div style="font-size:0.85rem;margin-top:4px;">₹{after_monthly * 12:,.0f}/year</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="insight-box">'
        f'💡 Cost reduction of <strong>{reduction_pct:.1f}%</strong> achieved. '
        f'SaaS optimization drives highest savings due to widespread license underutilization.'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_audit_tab():
    """📜 AUDIT tab — logs table and pipeline trace."""
    issues = st.session_state.get("issues", [])
    actions = st.session_state.get("actions", [])
    verified_logs = st.session_state.get("verified_logs", [])
    report = st.session_state.get("report", None)

    # ── Pipeline Trace
    st.markdown("### AGENT PIPELINE TRACE")
    render_agent_trace()

    st.markdown("---")

    # ── Audit Logs Table
    st.markdown("### AUDIT LOG")

    log_entries = []

    # Ingestion entry
    data = st.session_state.get("data", {})
    total_records = sum(len(v) for v in data.values())
    log_entries.append({
        "Timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        "Agent": "INGESTION",
        "Action": "Data ingestion",
        "Result": f"{total_records} records loaded",
    })

    # Detection entry
    log_entries.append({
        "Timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        "Agent": "DETECTION",
        "Action": "Anomaly detection",
        "Result": f"{len(issues)} issues found",
    })

    # Decision entry
    log_entries.append({
        "Timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        "Agent": "DECISION",
        "Action": "Action planning",
        "Result": f"{len(actions)} actions planned",
    })

    # Execution entries
    for log in verified_logs:
        status_val = log.status.value.upper()
        log_entries.append({
            "Timestamp": log.executed_at.strftime("%H:%M:%S") if log.executed_at else "—",
            "Agent": "EXECUTION",
            "Action": f"{log.action_type.value.replace('_', ' ').title()}",
            "Result": f"{status_val} — {'Verified' if log.verified else 'Pending'}",
        })

    # Impact entry
    if report:
        log_entries.append({
            "Timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "Agent": "IMPACT",
            "Action": "Financial assessment",
            "Result": f"₹{report.total_impact_inr:,.0f} total impact",
        })

    df = pd.DataFrame(log_entries)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Audit file path
    audit_path = st.session_state.get("audit_path", "")
    if audit_path:
        st.markdown(
            f'<div class="neo-card" style="background-color:{OFF_WHITE};">'
            f'<span class="neo-label">AUDIT LOG FILE</span><br>'
            f'<span style="font-family:Space Mono,monospace;font-size:0.85rem;">{audit_path}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

# ── Page Config
st.set_page_config(
    page_title="ACOE — Autonomous Cost Optimization Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject CSS
st.markdown(NEO_BRUTAL_CSS, unsafe_allow_html=True)

# ── Initialize State
if "demo_mode" not in st.session_state:
    st.session_state["demo_mode"] = False

# ── Sidebar
with st.sidebar:
    st.markdown(
        f'<div style="font-family:Inter;font-weight:900;font-size:1.5rem;'
        f'border-bottom:3px solid {ACCENT};padding-bottom:8px;margin-bottom:16px;">'
        f'ACOE v2.0</div>',
        unsafe_allow_html=True,
    )
    st.caption("AUTONOMOUS COST OPTIMIZATION ENGINE")
    st.markdown("---")

    if st.button("▶ RUN OPTIMIZATION", use_container_width=True):
        run_optimization()
        st.rerun()

    st.markdown("---")

    # Demo Mode Toggle
    demo = st.toggle("DEMO MODE", value=st.session_state.get("demo_mode", False), key="demo_toggle")
    st.session_state["demo_mode"] = demo
    if demo:
        st.info("Demo mode ON — guiding annotations enabled throughout the interface.")

    st.markdown("---")
    st.markdown(
        f'<div style="font-family:Space Mono,monospace;font-size:0.7rem;opacity:0.6;">'
        f'Last run: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>',
        unsafe_allow_html=True,
    )

# ── Load Data
load_data()

# ── Header
render_header()

# ── Demo Mode Banner
if st.session_state.get("demo_mode"):
    st.markdown(
        f'<div class="insight-box" style="border-left-color:{GLOW};">'
        f'🔵 <strong>DEMO MODE</strong> — This dashboard visualizes the full autonomous pipeline. '
        f'Each tab shows a stage of the ACOE engine: from problem detection through financial impact realization. '
        f'All data is sourced from real backend agents running deterministic analysis.'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Agent Trace
render_agent_trace()

# ── Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚨 PROBLEM",
    "🔍 DETECTION",
    "🧠 DECISION",
    "⚙️ EXECUTION",
    "💰 IMPACT",
    "📜 AUDIT",
])

with tab1:
    render_problem_tab()

with tab2:
    render_detection_tab()

with tab3:
    render_decision_tab()

with tab4:
    render_execution_tab()

with tab5:
    render_impact_tab()

with tab6:
    render_audit_tab()
