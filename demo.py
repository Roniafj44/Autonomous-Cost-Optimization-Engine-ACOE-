"""
ACOE -- Deterministic Demo Script
Runs the full pipeline once and shows BEFORE vs AFTER with INR savings.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from agents.ingestion import IngestionAgent
from agents.detection import DetectionAgent
from agents.decision import DecisionAgent
from agents.execution import ExecutionAgent
from agents.verification import VerificationAgent
from agents.audit import AuditAgent
from agents.impact import ImpactAgent


def banner(text: str, char: str = "="):
    width = 70
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def section(text: str):
    print(f"\n>> {text}")
    print("-" * 50)


def main():
    banner("ACOE -- AUTONOMOUS COST OPTIMIZATION ENGINE")
    print("  Deterministic Demo Run")
    print("  Mode: DEMO (seed=42)")
    print(f"  Data: {config.DATA_DIR}")

    start = time.time()

    # ── STEP 1: INGEST ───────────────────────────────────────────
    section("STEP 1: Data Ingestion")
    ingestion = IngestionAgent()
    data = ingestion.run()
    for source, records in data.items():
        print(f"  {source:20s}: {len(records)} records")
    total_records = sum(len(v) for v in data.values())
    print(f"  {'TOTAL':20s}: {total_records} records")

    # ── BEFORE STATE ─────────────────────────────────────────────
    total_spend = 0
    banner("BEFORE: Current Enterprise Spend", "-")
    print(f"\n  {'Category':<30s} {'Count':<8s} {'Monthly Spend (INR)':<20s}")
    print(f"  {'-'*30} {'-'*8} {'-'*20}")

    proc_spend = sum(r.contract_value_inr / 12 for r in data["procurement"])
    saas_spend = sum(s.monthly_cost_inr for s in data["saas"])
    cloud_spend = sum(c.monthly_cost_inr for c in data["cloud"])
    penalty_risk = sum(s.breach_penalty_inr for s in data["sla"])

    print(f"  {'Procurement Contracts':<30s} {len(data['procurement']):<8d} INR {proc_spend:>14,.0f}")
    print(f"  {'SaaS Subscriptions':<30s} {len(data['saas']):<8d} INR {saas_spend:>14,.0f}")
    print(f"  {'Cloud Resources':<30s} {len(data['cloud']):<8d} INR {cloud_spend:>14,.0f}")
    print(f"  {'SLA Penalty Exposure':<30s} {len(data['sla']):<8d} INR {penalty_risk:>14,.0f}")
    total_spend = proc_spend + saas_spend + cloud_spend
    print(f"\n  {'TOTAL MONTHLY SPEND':<30s} {'':8s} INR {total_spend:>14,.0f}")
    print(f"  {'ANNUAL EXPOSURE':<30s} {'':8s} INR {total_spend * 12:>14,.0f}")

    # ── STEP 2: DETECT ───────────────────────────────────────────
    section("STEP 2: Anomaly Detection")
    detection = DetectionAgent()
    issues = detection.run(data)
    print(f"\n  Total issues detected: {len(issues)}")
    print(f"\n  {'#':<4s} {'Severity':<10s} {'Category':<25s} {'Title':<40s} {'Savings (INR)':<15s}")
    print(f"  {'-'*4} {'-'*10} {'-'*25} {'-'*40} {'-'*15}")
    for i, issue in enumerate(issues, 1):
        print(
            f"  {i:<4d} {issue.severity.value.upper():<10s} "
            f"{issue.category.value:<25s} {issue.title[:39]:<40s} "
            f"INR {issue.potential_savings_inr:>11,.0f}"
        )

    # ── STEP 3: DECIDE ───────────────────────────────────────────
    section("STEP 3: Action Planning")
    decision = DecisionAgent()
    actions = decision.run(issues)
    print(f"\n  Actions generated: {len(actions)}")
    print(f"\n  {'#':<4s} {'Type':<22s} {'Title':<35s} {'ROI':<6s} {'Risk':<6s} {'Conf':<6s} {'Savings (INR)':<15s}")
    print(f"  {'-'*4} {'-'*22} {'-'*35} {'-'*6} {'-'*6} {'-'*6} {'-'*15}")
    for i, action in enumerate(actions, 1):
        print(
            f"  {i:<4d} {action.action_type.value:<22s} "
            f"{action.title[:34]:<35s} "
            f"{action.roi_estimate:<5.1f}x {action.risk_score:<5.0%} {action.confidence_score:<5.0%} "
            f"INR {action.estimated_savings_inr:>11,.0f}"
        )

    # ── STEP 4: EXECUTE ──────────────────────────────────────────
    section("STEP 4: Autonomous Execution")
    execution = ExecutionAgent()
    exec_logs = execution.run(actions)
    executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
    failed = sum(1 for l in exec_logs if l.status.value == "failed")
    skipped = sum(1 for l in exec_logs if l.status.value == "skipped")
    print(f"  Executed: {executed} | Failed: {failed} | Skipped: {skipped}")

    # ── STEP 5: VERIFY ───────────────────────────────────────────
    section("STEP 5: Outcome Verification")
    verification = VerificationAgent()
    verified = verification.run(actions, exec_logs)
    v_count = sum(1 for l in verified if l.verified)
    print(f"  Verified: {v_count}/{len(verified)}")

    # ── STEP 6: IMPACT ───────────────────────────────────────────
    section("STEP 6: Financial Impact")
    impact = ImpactAgent()
    report = impact.run(1, actions, verified, issues)

    # ── AFTER STATE ──────────────────────────────────────────────
    banner("AFTER: Optimized State", "-")
    monthly_savings = report.total_impact_inr / 12
    print(f"\n  {'Metric':<35s} {'Value (INR)':<20s}")
    print(f"  {'-'*35} {'-'*20}")
    print(f"  {'Realized Monthly Savings':<35s} INR {report.realized_savings_inr:>14,.0f}")
    print(f"  {'Projected Annual Savings':<35s} INR {report.projected_annual_savings_inr:>14,.0f}")
    print(f"  {'Avoided SLA Penalties':<35s} INR {report.avoided_penalties_inr:>14,.0f}")
    print(f"  {'TOTAL IMPACT':<35s} INR {report.total_impact_inr:>14,.0f}")

    # ── BEFORE vs AFTER ──────────────────────────────────────────
    banner("BEFORE vs AFTER COMPARISON", "=")
    optimized_monthly = total_spend - monthly_savings
    reduction_pct = (monthly_savings / total_spend * 100) if total_spend > 0 else 0

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
    print(f"\n  Cost Reduction: {reduction_pct:.1f}%")
    print(f"  Issues Detected: {len(issues)}")
    print(f"  Actions Taken: {executed}")
    print(f"  Verification Rate: {v_count}/{len(verified)} ({v_count/max(len(verified),1)*100:.0f}%)")

    elapsed = time.time() - start
    banner(f"DEMO COMPLETE in {elapsed:.2f}s", "=")
    print(f"  Total Savings: INR {report.total_impact_inr:,.0f}")
    print(f"  Zero human intervention required.\n")


if __name__ == "__main__":
    main()
