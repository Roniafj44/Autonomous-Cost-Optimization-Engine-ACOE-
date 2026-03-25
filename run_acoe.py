#!/usr/bin/env python3
"""
====================================================================
  AUTONOMOUS COST OPTIMIZATION ENGINE (ACOE)
  Single-Command Entry Point — Judge-Ready Demonstration
====================================================================

  python run_acoe.py

  This command:
    1. Starts the autonomous engine
    2. Runs the full 7-stage pipeline IMMEDIATELY
    3. Shows BEFORE vs AFTER with INR savings
    4. Continues the autonomous loop indefinitely

  ZERO human intervention required after execution.
====================================================================
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import signal
import time
import threading
from datetime import datetime

# ── Environment ──────────────────────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from agents.ingestion import IngestionAgent
from agents.detection import DetectionAgent
from agents.decision import DecisionAgent
from agents.execution import ExecutionAgent
from agents.verification import VerificationAgent
from agents.audit import AuditAgent
from agents.impact import ImpactAgent

# ── ANSI Colors ──────────────────────────────────────────────────────────────
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
WHITE   = "\033[97m"
BG_GREEN  = "\033[42m"
BG_RED    = "\033[41m"
BG_BLUE   = "\033[44m"
BG_YELLOW = "\033[43m"


def P(text=""):
    """Safe print with encoding fallback."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode())


def banner(title, char="=", color=CYAN):
    w = 72
    P(f"\n{color}{BOLD}{char * w}")
    P(f"  {title}")
    P(f"{char * w}{RESET}")


def section(title, icon=">>", color=YELLOW):
    P(f"\n{color}{BOLD}{icon} {title}{RESET}")
    P(f"{DIM}{'─' * 60}{RESET}")


def status_line(label, value, color=GREEN):
    P(f"  {BOLD}{label:<38s}{RESET} {color}{value}{RESET}")


def issue_block(num, issue):
    """Print a single detected issue in judge-optimized format."""
    sev = issue.severity.value.upper()
    sev_colors = {"CRITICAL": RED, "HIGH": YELLOW, "MEDIUM": CYAN, "LOW": DIM}
    sc = sev_colors.get(sev, WHITE)

    P(f"\n  {DIM}┌─────────────────────────────────────────────────────────────┐{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}[DETECTED ISSUE #{num}]{RESET}")
    P(f"  {DIM}│{RESET} Severity: {sc}{BOLD}{sev}{RESET}")
    P(f"  {DIM}│{RESET} Category: {issue.category.value}")
    P(f"  {DIM}│{RESET} {issue.title}")
    P(f"  {DIM}│{RESET} Potential Savings: {GREEN}INR {issue.potential_savings_inr:,.0f}/year{RESET}")
    P(f"  {DIM}└─────────────────────────────────────────────────────────────┘{RESET}")


def action_block(num, action):
    """Print a single action plan in judge-optimized format."""
    P(f"\n  {DIM}┌─────────────────────────────────────────────────────────────┐{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}[DECISION #{num}]{RESET}")
    P(f"  {DIM}│{RESET} Action: {CYAN}{action.action_type.value}{RESET}")
    P(f"  {DIM}│{RESET} Target: {action.title}")
    P(f"  {DIM}│{RESET} Confidence: {GREEN}{action.confidence_score:.0%}{RESET}  |  Risk: {YELLOW}{action.risk_score:.0%}{RESET}  |  ROI: {GREEN}{action.roi_estimate:.1f}x{RESET}")
    P(f"  {DIM}│{RESET} Estimated Savings: {GREEN}{BOLD}INR {action.estimated_savings_inr:,.0f}{RESET}")
    P(f"  {DIM}└─────────────────────────────────────────────────────────────┘{RESET}")


def exec_block(num, action, log):
    """Print execution result in judge-optimized format."""
    ok = log.status.value in ("executed", "verified")
    icon = f"{GREEN}SUCCESS{RESET}" if ok else f"{RED}FAILED{RESET}"
    api_calls = {
        "cancel_subscription": "cancel_subscription()",
        "downgrade_plan": "downgrade_plan()",
        "consolidate_vendors": "consolidate_vendors()",
        "reallocate_compute": "reallocate_compute()",
        "trigger_escalation": "trigger_escalation()",
        "renegotiate_contract": "renegotiate_contract()",
    }
    api = api_calls.get(action.action_type.value, "execute_action()")

    P(f"\n  {DIM}┌─────────────────────────────────────────────────────────────┐{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}[EXECUTION #{num}]{RESET}")
    P(f"  {DIM}│{RESET} Action: {action.title}")
    P(f"  {DIM}│{RESET} Status: {icon}")
    P(f"  {DIM}│{RESET} API Call: {CYAN}{api}{RESET}")
    P(f"  {DIM}│{RESET} Attempts: {log.attempts}  |  Verified: {'Yes' if log.verified else 'Pending'}")
    P(f"  {DIM}└─────────────────────────────────────────────────────────────┘{RESET}")


def impact_block(label, monthly, annual):
    """Print a single impact line."""
    P(f"  {DIM}│{RESET} {label:<30s}  Monthly: {GREEN}INR {monthly:>12,.0f}{RESET}  |  Annual: {GREEN}INR {annual:>14,.0f}{RESET}")


def delay(seconds=0.05):
    """Tiny delay for dramatic effect in demo."""
    time.sleep(seconds)


# ═══════════════════════════════════════════════════════════════════════════════
#   MAIN DEMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_demonstration():
    """Run the full judge-centric demonstration."""

    start_time = time.time()

    # ── STARTUP BANNER ───────────────────────────────────────────────────
    P(f"\n{CYAN}{BOLD}")
    P(f"    ╔══════════════════════════════════════════════════════════════════╗")
    P(f"    ║                                                                ║")
    P(f"    ║   AUTONOMOUS COST OPTIMIZATION ENGINE (ACOE)                   ║")
    P(f"    ║   Self-Driving Financial Optimization System                   ║")
    P(f"    ║                                                                ║")
    P(f"    ║   Version:  2.0.0                                              ║")
    P(f"    ║   Mode:     FULLY AUTONOMOUS                                   ║")
    P(f"    ║   Status:   INITIALIZING...                                    ║")
    P(f"    ║                                                                ║")
    P(f"    ╚══════════════════════════════════════════════════════════════════╝")
    P(f"{RESET}")

    delay(0.3)
    P(f"\n  {GREEN}{BOLD}>>> Autonomous loop started{RESET}")
    P(f"  {GREEN}{BOLD}>>> No human intervention required{RESET}")
    P(f"  {GREEN}{BOLD}>>> All decisions are made by the AI engine{RESET}")
    delay(0.2)

    # Initialize agents
    P(f"\n  {DIM}Initializing multi-agent pipeline...{RESET}")
    ingestion = IngestionAgent()
    detection = DetectionAgent()
    decision = DecisionAgent()
    execution = ExecutionAgent()
    verification = VerificationAgent()
    audit = AuditAgent()
    impact = ImpactAgent()
    P(f"  {GREEN}[OK]{RESET} 7 autonomous agents initialized")
    delay(0.1)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 1: DATA INGESTION
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 1: AUTONOMOUS DATA INGESTION", "=", CYAN)
    P(f"\n  {MAGENTA}Evaluating system state...{RESET}")
    P(f"  {MAGENTA}Scanning enterprise data sources...{RESET}")
    delay(0.1)

    data = ingestion.run()
    total_records = sum(len(v) for v in data.values())

    P(f"\n  {GREEN}[OK]{RESET} Data ingestion complete")
    P(f"  {DIM}{'─' * 50}{RESET}")
    status_line("Procurement Contracts", f"{len(data['procurement'])} records")
    status_line("SaaS Subscriptions", f"{len(data['saas'])} records")
    status_line("Cloud Resources", f"{len(data['cloud'])} records")
    status_line("SLA Metrics", f"{len(data['sla'])} records")
    P(f"  {DIM}{'─' * 50}{RESET}")
    status_line("TOTAL RECORDS INGESTED", f"{BOLD}{total_records}{RESET}")

    # ══════════════════════════════════════════════════════════════════════
    #  BEFORE STATE — Current Enterprise Spend
    # ══════════════════════════════════════════════════════════════════════
    banner("BEFORE STATE: Current Enterprise Spend", "=", RED)

    proc_monthly = sum(r.contract_value_inr / 12 for r in data["procurement"])
    saas_monthly = sum(s.monthly_cost_inr for s in data["saas"])
    cloud_monthly = sum(c.monthly_cost_inr for c in data["cloud"])
    penalty_exposure = sum(s.breach_penalty_inr for s in data["sla"])
    total_monthly = proc_monthly + saas_monthly + cloud_monthly

    P(f"\n  {BOLD}{'Category':<35s} {'Monthly (INR)':<20s} {'Annual (INR)':<20s}{RESET}")
    P(f"  {'─' * 75}")
    P(f"  {'Procurement Contracts':<35s} {RED}INR {proc_monthly:>14,.0f}{RESET}  {RED}INR {proc_monthly*12:>14,.0f}{RESET}")
    P(f"  {'SaaS Subscriptions':<35s} {RED}INR {saas_monthly:>14,.0f}{RESET}  {RED}INR {saas_monthly*12:>14,.0f}{RESET}")
    P(f"  {'Cloud Infrastructure':<35s} {RED}INR {cloud_monthly:>14,.0f}{RESET}  {RED}INR {cloud_monthly*12:>14,.0f}{RESET}")
    P(f"  {'SLA Penalty Exposure':<35s} {RED}{'─':>18s}{RESET}  {RED}INR {penalty_exposure:>14,.0f}{RESET}")
    P(f"  {'─' * 75}")
    P(f"  {BOLD}{RED}{'TOTAL OPERATIONAL SPEND':<35s} INR {total_monthly:>14,.0f}  INR {total_monthly*12:>14,.0f}{RESET}")

    delay(0.2)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 2: ANOMALY DETECTION
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 2: IDENTIFYING INEFFICIENCIES", "=", YELLOW)
    P(f"\n  {MAGENTA}Identifying inefficiencies...{RESET}")
    P(f"  {MAGENTA}Running rule-based heuristics + z-score anomaly detection...{RESET}")
    delay(0.1)

    issues = detection.run(data)

    P(f"\n  {GREEN}[OK]{RESET} Detection complete: {BOLD}{len(issues)} inefficiencies found{RESET}")

    # Show top issues with full formatting
    for i, issue in enumerate(issues[:8], 1):
        issue_block(i, issue)
        delay(0.02)

    if len(issues) > 8:
        P(f"\n  {DIM}... and {len(issues) - 8} more issues detected{RESET}")

    total_potential = sum(iss.potential_savings_inr for iss in issues)
    P(f"\n  {BOLD}Total Potential Savings Identified: {GREEN}INR {total_potential:,.0f}/year{RESET}")

    delay(0.2)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 3: AUTONOMOUS DECISION-MAKING
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 3: AUTONOMOUS DECISION-MAKING", "=", CYAN)
    P(f"\n  {MAGENTA}Evaluating corrective actions...{RESET}")
    P(f"  {MAGENTA}Computing ROI, risk, and confidence scores...{RESET}")
    delay(0.1)

    actions = decision.run(issues)

    P(f"\n  {GREEN}[OK]{RESET} Decision engine generated {BOLD}{len(actions)} action plans{RESET}")

    for i, action in enumerate(actions[:6], 1):
        action_block(i, action)
        delay(0.02)

    if len(actions) > 6:
        P(f"\n  {DIM}... and {len(actions) - 6} more actions planned{RESET}")

    delay(0.2)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 4: AUTONOMOUS EXECUTION
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 4: EXECUTING OPTIMIZATION ACTIONS", "=", MAGENTA)
    P(f"\n  {MAGENTA}Executing optimization actions...{RESET}")
    P(f"  {MAGENTA}No human approval required — autonomous mode active{RESET}")
    delay(0.1)

    exec_logs = execution.run(actions)

    executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
    failed = sum(1 for l in exec_logs if l.status.value == "failed")

    # Show first several executions
    for i, (action, log) in enumerate(zip(actions[:5], exec_logs[:5]), 1):
        exec_block(i, action, log)
        delay(0.02)

    if len(actions) > 5:
        P(f"\n  {DIM}... and {len(actions) - 5} more actions executed{RESET}")

    P(f"\n  {GREEN}[OK]{RESET} Execution complete: {BOLD}{executed}/{len(exec_logs)} successful{RESET}, {failed} failed")
    P(f"  {GREEN}{BOLD}>>> Taking corrective action... DONE{RESET}")

    delay(0.2)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 5: OUTCOME VERIFICATION
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 5: VERIFYING EXECUTION OUTCOMES", "=", CYAN)
    P(f"\n  {MAGENTA}Verifying execution outcomes...{RESET}")
    P(f"  {MAGENTA}Running 4-point verification: status + message + entity + deviation{RESET}")
    delay(0.1)

    verified_logs = verification.run(actions, exec_logs)
    v_count = sum(1 for l in verified_logs if l.verified)

    P(f"\n  {GREEN}[OK]{RESET} Verification: {BOLD}{v_count}/{len(verified_logs)} actions verified{RESET}")
    P(f"  {GREEN}[OK]{RESET} Verification rate: {BOLD}{v_count/max(len(verified_logs),1)*100:.0f}%{RESET}")

    delay(0.1)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 6: AUDIT LOGGING
    # ══════════════════════════════════════════════════════════════════════
    section("STAGE 6: AUDIT TRAIL — Full decision chain logged", ">>", DIM)
    log_path = audit.run(1, data, issues, actions, verified_logs, None)
    P(f"  {GREEN}[OK]{RESET} Audit log: {DIM}{log_path}{RESET}")

    delay(0.1)

    # ══════════════════════════════════════════════════════════════════════
    #  STAGE 7: FINANCIAL IMPACT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════
    banner("STAGE 7: FINANCIAL IMPACT REALIZED", "=", GREEN)
    P(f"\n  {MAGENTA}Financial impact realized...{RESET}")
    P(f"  {MAGENTA}Computing realized savings, projected annual, and avoided penalties...{RESET}")
    delay(0.1)

    report = impact.run(1, actions, verified_logs, issues)

    # Rewrite the audit with impact
    audit.run(1, data, issues, actions, verified_logs, report)

    P(f"\n  {DIM}┌──────────────────────────────────────────────────────────────────┐{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}{GREEN}[IMPACT REPORT]{RESET}")
    P(f"  {DIM}│{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}Realized Monthly Savings:{RESET}    {GREEN}{BOLD}INR {report.realized_savings_inr:>14,.0f}{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}Projected Annual Savings:{RESET}    {GREEN}{BOLD}INR {report.projected_annual_savings_inr:>14,.0f}{RESET}")
    P(f"  {DIM}│{RESET} {BOLD}Avoided SLA Penalties:{RESET}       {GREEN}{BOLD}INR {report.avoided_penalties_inr:>14,.0f}{RESET}")
    P(f"  {DIM}│{RESET} {'─' * 56}")
    P(f"  {DIM}│{RESET} {BOLD}TOTAL FINANCIAL IMPACT:{RESET}      {GREEN}{BOLD}INR {report.total_impact_inr:>14,.0f}{RESET}")
    P(f"  {DIM}│{RESET}")
    P(f"  {DIM}└──────────────────────────────────────────────────────────────────┘{RESET}")

    delay(0.2)

    # ══════════════════════════════════════════════════════════════════════
    #  BEFORE vs AFTER COMPARISON
    # ══════════════════════════════════════════════════════════════════════
    monthly_savings = report.total_impact_inr / 12
    after_monthly = total_monthly - monthly_savings
    reduction_pct = (monthly_savings / total_monthly * 100) if total_monthly > 0 else 0

    P(f"\n{BOLD}{CYAN}")
    P(f"    ╔══════════════════════════════════════════════════════════════════╗")
    P(f"    ║                                                                ║")
    P(f"    ║              BEFORE  vs  AFTER  COMPARISON                     ║")
    P(f"    ║                                                                ║")
    P(f"    ╠══════════════════════════════════════════════════════════════════╣")
    P(f"    ║                                                                ║")
    P(f"    ║  {RED}BEFORE Optimization:{RESET}{BOLD}{CYAN}                                       ║")
    P(f"    ║    Monthly Spend:  {RED}INR {total_monthly:>14,.0f}{RESET}{BOLD}{CYAN}                       ║")
    P(f"    ║    Annual Spend:   {RED}INR {total_monthly*12:>14,.0f}{RESET}{BOLD}{CYAN}                       ║")
    P(f"    ║                                                                ║")
    P(f"    ║  {GREEN}AFTER Optimization:{RESET}{BOLD}{CYAN}                                        ║")
    P(f"    ║    Monthly Spend:  {GREEN}INR {after_monthly:>14,.0f}{RESET}{BOLD}{CYAN}                       ║")
    P(f"    ║    Annual Spend:   {GREEN}INR {after_monthly*12:>14,.0f}{RESET}{BOLD}{CYAN}                       ║")
    P(f"    ║                                                                ║")
    P(f"    ║  ──────────────────────────────────────────────────             ║")
    P(f"    ║                                                                ║")
    P(f"    ║  {GREEN}{BOLD}TOTAL SAVINGS:     INR {report.total_impact_inr:>14,.0f}/year{RESET}{BOLD}{CYAN}              ║")
    P(f"    ║  {GREEN}{BOLD}COST REDUCTION:    {reduction_pct:.1f}%{RESET}{BOLD}{CYAN}                                    ║")
    P(f"    ║                                                                ║")
    P(f"    ╚══════════════════════════════════════════════════════════════════╝")
    P(f"{RESET}")

    # ── CYCLE SUMMARY ────────────────────────────────────────────────────
    elapsed = time.time() - start_time

    P(f"\n  {DIM}{'─' * 60}{RESET}")
    P(f"  {BOLD}CYCLE SUMMARY{RESET}")
    P(f"  {DIM}{'─' * 60}{RESET}")
    status_line("Records Ingested", f"{total_records}")
    status_line("Issues Detected", f"{len(issues)}")
    status_line("Actions Planned", f"{len(actions)}")
    status_line("Actions Executed", f"{executed}/{len(exec_logs)}")
    status_line("Actions Verified", f"{v_count}/{len(verified_logs)}")
    status_line("Total Savings", f"INR {report.total_impact_inr:,.0f}")
    status_line("Cost Reduction", f"{reduction_pct:.1f}%")
    status_line("Execution Time", f"{elapsed:.2f}s")
    status_line("Human Intervention", f"{RED}NONE — Fully Autonomous{RESET}")
    P(f"  {DIM}{'─' * 60}{RESET}")

    P(f"\n  {GREEN}{BOLD}>>> Optimization cycle complete.{RESET}")
    P(f"  {GREEN}{BOLD}>>> Financial impact realized: INR {report.total_impact_inr:,.0f}{RESET}")
    P(f"  {GREEN}{BOLD}>>> Cumulative savings: INR {report.total_impact_inr:,.0f}{RESET}")

    return report.total_impact_inr


# ═══════════════════════════════════════════════════════════════════════════════
#   AUTONOMOUS LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def run_autonomous_loop(cumulative_savings: float):
    """Continue the autonomous loop after initial demonstration."""
    cycle = 2
    P(f"\n\n{CYAN}{BOLD}{'=' * 72}")
    P(f"  ENTERING CONTINUOUS AUTONOMOUS MODE")
    P(f"  The system will now run indefinitely, detecting and optimizing costs.")
    P(f"  Press Ctrl+C to stop.")
    P(f"{'=' * 72}{RESET}")

    while True:
        try:
            P(f"\n  {DIM}Next cycle in {config.LOOP_INTERVAL_SECONDS:.0f}s...{RESET}")
            time.sleep(config.LOOP_INTERVAL_SECONDS)

            P(f"\n{CYAN}{BOLD}{'─' * 72}")
            P(f"  AUTONOMOUS CYCLE #{cycle}")
            P(f"{'─' * 72}{RESET}")
            P(f"\n  {MAGENTA}Evaluating system state...{RESET}")

            ingestion = IngestionAgent()
            detection = DetectionAgent()
            decision_ = DecisionAgent()
            execution_ = ExecutionAgent()
            verification_ = VerificationAgent()
            audit_ = AuditAgent()
            impact_ = ImpactAgent()

            data = ingestion.run()
            issues = detection.run(data)
            actions = decision_.run(issues)

            # Idempotency: skip already-executed actions
            execution_.load_executed_keys([])
            exec_logs = execution_.run(actions)
            verified = verification_.run(actions, exec_logs)
            report = impact_.run(cycle, actions, verified, issues)
            audit_.run(cycle, data, issues, actions, verified, report)

            cumulative_savings += report.total_impact_inr
            executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))

            P(f"\n  {GREEN}[OK]{RESET} Cycle #{cycle} complete")
            P(f"  Issues: {len(issues)} | Actions: {executed}/{len(actions)} | Savings: INR {report.total_impact_inr:,.0f}")
            P(f"  {GREEN}{BOLD}>>> Cumulative savings: INR {cumulative_savings:,.0f}{RESET}")
            P(f"  {GREEN}{BOLD}>>> Optimization cycle complete.{RESET}")

            cycle += 1

        except KeyboardInterrupt:
            P(f"\n\n  {YELLOW}{BOLD}>>> Graceful shutdown initiated{RESET}")
            P(f"  {GREEN}>>> Total cycles run: {cycle - 1}{RESET}")
            P(f"  {GREEN}>>> Final cumulative savings: INR {cumulative_savings:,.0f}{RESET}")
            P(f"  {GREEN}>>> ACOE daemon stopped.{RESET}\n")
            break
        except Exception as e:
            P(f"\n  {RED}[ERR]{RESET} Cycle #{cycle} failed: {e}")
            P(f"  {YELLOW}Self-recovering... will retry next cycle.{RESET}")
            cycle += 1


# ═══════════════════════════════════════════════════════════════════════════════
#   ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("color")

    try:
        savings = run_demonstration()
        run_autonomous_loop(savings)
    except KeyboardInterrupt:
        P(f"\n  {YELLOW}Shutdown.{RESET}")
    except Exception as e:
        P(f"\n  {RED}Fatal error: {e}{RESET}")
        import traceback
        traceback.print_exc()
