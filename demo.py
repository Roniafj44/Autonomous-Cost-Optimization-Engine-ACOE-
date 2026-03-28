"""
ACOE -- Deterministic Demo Script
Runs the full pipeline once and shows BEFORE vs AFTER with INR savings.

HOW TO RUN:
    python demo.py

This is a clean, single-cycle demo designed for quick inspection.
Use run_acoe.py for the full autonomous loop with ANSI colors.
"""

from __future__ import annotations

import os
import sys
import time

# ── Add the project root to Python's module search path ──────────────────────
# This is needed so Python can find the agents/ and models/ packages
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # Loads config from config.yaml (thresholds, intervals, etc.)

# ── Import the 7 autonomous agents (one per pipeline stage) ──────────────────
from agents.ingestion import IngestionAgent       # Stage 1: Load data from CSVs
from agents.detection import DetectionAgent       # Stage 2: Detect inefficiencies
from agents.decision import DecisionAgent         # Stage 3: Plan corrective actions
from agents.execution import ExecutionAgent       # Stage 4: Execute actions
from agents.verification import VerificationAgent # Stage 5: Verify outcomes
from agents.audit import AuditAgent               # Stage 6: Log audit trail
from agents.impact import ImpactAgent             # Stage 7: Calculate financial impact


# ── Helper: Print a wide banner separator ────────────────────────────────────
def banner(text: str, char: str = "="):
    width = 70
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


# ── Helper: Print a small section header ─────────────────────────────────────
def section(text: str):
    print(f"\n>> {text}")
    print("-" * 50)


def main():
    # Print top-level banner with config data directory path
    banner("ACOE -- AUTONOMOUS COST OPTIMIZATION ENGINE")
    print("  Deterministic Demo Run")
    print("  Mode: DEMO (seed=42)")         # seed=42 ensures same output every run
    print(f"  Data: {config.DATA_DIR}")     # Shows where data/ folder is located

    start = time.time()  # Track how long the full pipeline takes

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 1: DATA INGESTION
    # Reads 4 CSV files and converts rows into structured Python objects
    # Files: procurement.csv, saas_subscriptions.csv, cloud_usage.csv, sla_metrics.csv
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 1: Data Ingestion")
    ingestion = IngestionAgent()
    data = ingestion.run()  # Returns dict: {procurement: [...], saas: [...], cloud: [...], sla: [...]}

    # Print count of records loaded from each source
    for source, records in data.items():
        print(f"  {source:20s}: {len(records)} records")

    total_records = sum(len(v) for v in data.values())  # Total rows across all files
    print(f"  {'TOTAL':20s}: {total_records} records")

    # ══════════════════════════════════════════════════════════════════════════
    # BEFORE STATE — Calculate current enterprise spend BEFORE optimization
    # This is what we compare against after the pipeline runs
    # ══════════════════════════════════════════════════════════════════════════
    total_spend = 0
    banner("BEFORE: Current Enterprise Spend", "-")
    print(f"\n  {'Category':<30s} {'Count':<8s} {'Monthly Spend (INR)':<20s}")
    print(f"  {'-'*30} {'-'*8} {'-'*20}")

    # Calculate monthly spend per category
    proc_spend = sum(r.contract_value_inr / 12 for r in data["procurement"])  # Annual → monthly
    saas_spend = sum(s.monthly_cost_inr for s in data["saas"])                # Already monthly
    cloud_spend = sum(c.monthly_cost_inr for c in data["cloud"])              # Already monthly
    penalty_risk = sum(s.breach_penalty_inr for s in data["sla"])             # SLA penalty exposure

    # Print each category row
    print(f"  {'Procurement Contracts':<30s} {len(data['procurement']):<8d} INR {proc_spend:>14,.0f}")
    print(f"  {'SaaS Subscriptions':<30s} {len(data['saas']):<8d} INR {saas_spend:>14,.0f}")
    print(f"  {'Cloud Resources':<30s} {len(data['cloud']):<8d} INR {cloud_spend:>14,.0f}")
    print(f"  {'SLA Penalty Exposure':<30s} {len(data['sla']):<8d} INR {penalty_risk:>14,.0f}")

    # Total monthly spend is the baseline we optimize against
    total_spend = proc_spend + saas_spend + cloud_spend
    print(f"\n  {'TOTAL MONTHLY SPEND':<30s} {'':8s} INR {total_spend:>14,.0f}")
    print(f"  {'ANNUAL EXPOSURE':<30s} {'':8s} INR {total_spend * 12:>14,.0f}")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2: ANOMALY DETECTION
    # Uses rule-based heuristics + z-score statistical analysis to find issues
    # Rules: low SaaS utilization, cloud over-provisioning, SLA near-breach, duplicate vendors
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 2: Anomaly Detection")
    detection = DetectionAgent()
    issues = detection.run(data)  # Returns list of CostIssue objects

    print(f"\n  Total issues detected: {len(issues)}")
    print(f"\n  {'#':<4s} {'Severity':<10s} {'Category':<25s} {'Title':<40s} {'Savings (INR)':<15s}")
    print(f"  {'-'*4} {'-'*10} {'-'*25} {'-'*40} {'-'*15}")

    # Print each detected issue with its severity and projected savings
    for i, issue in enumerate(issues, 1):
        print(
            f"  {i:<4d} {issue.severity.value.upper():<10s} "
            f"{issue.category.value:<25s} {issue.title[:39]:<40s} "
            f"INR {issue.potential_savings_inr:>11,.0f}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 3: ACTION PLANNING (DECISION)
    # For each detected issue, the AI generates a corrective action
    # Each action includes: type, estimated savings, confidence, risk, ROI
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 3: Action Planning")
    decision = DecisionAgent()
    actions = decision.run(issues)  # Returns list of ActionPlan objects

    print(f"\n  Actions generated: {len(actions)}")
    print(f"\n  {'#':<4s} {'Type':<22s} {'Title':<35s} {'ROI':<6s} {'Risk':<6s} {'Conf':<6s} {'Savings (INR)':<15s}")
    print(f"  {'-'*4} {'-'*22} {'-'*35} {'-'*6} {'-'*6} {'-'*6} {'-'*15}")

    # Print each planned action with scoring metrics
    for i, action in enumerate(actions, 1):
        print(
            f"  {i:<4d} {action.action_type.value:<22s} "
            f"{action.title[:34]:<35s} "
            f"{action.roi_estimate:<5.1f}x {action.risk_score:<5.0%} {action.confidence_score:<5.0%} "
            f"INR {action.estimated_savings_inr:>11,.0f}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 4: AUTONOMOUS EXECUTION
    # Executes each planned action with retry logic (up to MAX_RETRIES attempts)
    # No human approval required — fully autonomous
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 4: Autonomous Execution")
    execution = ExecutionAgent()
    exec_logs = execution.run(actions)  # Returns list of ExecutionLog objects

    # Count outcomes
    executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
    failed = sum(1 for l in exec_logs if l.status.value == "failed")
    skipped = sum(1 for l in exec_logs if l.status.value == "skipped")  # Already executed (idempotency)

    print(f"  Executed: {executed} | Failed: {failed} | Skipped: {skipped}")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 5: OUTCOME VERIFICATION
    # 4-point check: status, message, entity ID, deviation from expected outcome
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 5: Outcome Verification")
    verification = VerificationAgent()
    verified = verification.run(actions, exec_logs)  # Annotates logs with verified=True/False
    v_count = sum(1 for l in verified if l.verified)

    print(f"  Verified: {v_count}/{len(verified)}")

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 6: FINANCIAL IMPACT CALCULATION
    # Computes realized savings, projected annual savings, and avoided penalties
    # ══════════════════════════════════════════════════════════════════════════
    section("STEP 6: Financial Impact")
    impact = ImpactAgent()
    report = impact.run(1, actions, verified, issues)  # cycle_id=1 for first run

    # ── AFTER STATE ──────────────────────────────────────────────────────────
    banner("AFTER: Optimized State", "-")
    monthly_savings = report.total_impact_inr / 12  # Convert annual impact to monthly

    print(f"\n  {'Metric':<35s} {'Value (INR)':<20s}")
    print(f"  {'-'*35} {'-'*20}")
    print(f"  {'Realized Monthly Savings':<35s} INR {report.realized_savings_inr:>14,.0f}")
    print(f"  {'Projected Annual Savings':<35s} INR {report.projected_annual_savings_inr:>14,.0f}")
    print(f"  {'Avoided SLA Penalties':<35s} INR {report.avoided_penalties_inr:>14,.0f}")
    print(f"  {'TOTAL IMPACT':<35s} INR {report.total_impact_inr:>14,.0f}")

    # ── BEFORE vs AFTER COMPARISON ────────────────────────────────────────────
    banner("BEFORE vs AFTER COMPARISON", "=")
    optimized_monthly = total_spend - monthly_savings        # Spend after optimization
    reduction_pct = (monthly_savings / total_spend * 100) if total_spend > 0 else 0  # % cost reduction

    print(f"\n  {'':40s} {'BEFORE':>15s}   {'AFTER':>15s}   {'SAVED':>15s}")
    print(f"  {'-'*40} {'-'*15}   {'-'*15}   {'-'*15}")
    print(
        f"  {'Monthly Operational Spend':<40s} "
        f"INR {total_spend:>11,.0f}   INR {optimized_monthly:>11,.0f}   "
        f"INR {monthly_savings:>11,.0f}"
    )
    print(
        f"  {'Annual Spend':<40s} "
        f"INR {total_spend * 12:>11,.0f}   INR {optimized_monthly * 12:>11,.0f}   "
        f"INR {report.total_impact_inr:>11,.0f}"
    )

    # Summary stats
    print(f"\n  Cost Reduction: {reduction_pct:.1f}%")
    print(f"  Issues Detected: {len(issues)}")
    print(f"  Actions Taken: {executed}")
    print(f"  Verification Rate: {v_count}/{len(verified)} ({v_count/max(len(verified),1)*100:.0f}%)")

    elapsed = time.time() - start  # Total wall-clock time for the full pipeline

    banner(f"DEMO COMPLETE in {elapsed:.2f}s", "=")
    print(f"  Total Savings: INR {report.total_impact_inr:,.0f}")
    print(f"  Zero human intervention required.\n")


# ── Script Entry Point ────────────────────────────────────────────────────────
# Only runs if this file is executed directly (not when imported as a module)
if __name__ == "__main__":
    main()
