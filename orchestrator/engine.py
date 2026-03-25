"""
ACOE -- Pipeline Orchestrator v2
DAG-based autonomous loop with SQLite state, circuit breakers, safety, metrics, prediction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import config
from models.schemas import CycleState
from agents.ingestion import IngestionAgent
from agents.detection import DetectionAgent
from agents.decision import DecisionAgent
from agents.execution import ExecutionAgent
from agents.verification import VerificationAgent
from agents.audit import AuditAgent
from agents.impact import ImpactAgent

logger = logging.getLogger("acoe.orchestrator")


class ACOEOrchestrator:
    """
    Autonomous pipeline orchestrator v2.
    Integrates: SQLite state, circuit breakers, safety guard, metrics, prediction.
    """

    def __init__(self, state_db=None, cb_manager=None, safety=None,
                 metrics_tracker=None, simulation=None, predictor=None):
        # Agents
        self.ingestion = IngestionAgent()
        self.detection = DetectionAgent()
        self.decision = DecisionAgent()
        self.execution = ExecutionAgent()
        self.verification = VerificationAgent()
        self.audit = AuditAgent()
        self.impact = ImpactAgent()

        # v2 components (optional — graceful fallback)
        self.state_db = state_db
        self.cb_manager = cb_manager
        self.safety = safety
        self.metrics_tracker = metrics_tracker
        self.simulation = simulation
        self.predictor = predictor

        # Runtime state
        self._running = False
        self._cycle_count = state_db.get_cycle_count() if state_db else 0
        self._cumulative_savings = state_db.get_cumulative_savings() if state_db else 0.0

        # Latest results (for API)
        self.latest_data = {}
        self.latest_issues = []
        self.latest_actions = []
        self.latest_executions = []
        self.latest_report = None
        self.latest_predictions = {}
        self.latest_simulation = {}

        # Idempotency keys
        self._executed_keys = state_db.get_executed_keys() if state_db else []

    async def start(self):
        """Start the autonomous loop (used by legacy main.py)."""
        self._running = True
        logger.info("=" * 70)
        logger.info("  ACOE Autonomous Cost Optimization Engine -- STARTING")
        logger.info(f"  Mode: {'DEMO' if config.DEMO_MODE else 'PRODUCTION'}")
        logger.info(f"  Loop interval: {config.LOOP_INTERVAL_SECONDS}s")
        logger.info("=" * 70)

        while self._running:
            await self.trigger_cycle()
            if self._running:
                logger.info(f"Next cycle in {config.LOOP_INTERVAL_SECONDS:.0f}s...")
                await asyncio.sleep(config.LOOP_INTERVAL_SECONDS)

    async def trigger_cycle(self):
        """Run a single cycle. Called by scheduler or start loop."""
        await self._run_cycle()

    def stop(self):
        self._running = False
        logger.info("Orchestrator: shutdown requested")

    # ── Core Pipeline ────────────────────────────────────────────────────

    async def _run_cycle(self):
        self._cycle_count += 1
        cycle_id = self._cycle_count

        cycle = CycleState(
            cycle_id=cycle_id,
            started_at=datetime.utcnow(),
            status="running",
        )

        # Register cycle in DB
        if self.state_db:
            self.state_db.start_cycle(cycle_id)

        # Reset safety counters
        if self.safety:
            self.safety.reset_cycle()

        logger.info(f"\n{'=' * 70}")
        logger.info(f"  CYCLE #{cycle_id} -- STARTED at {cycle.started_at.isoformat()}")
        logger.info(f"{'=' * 70}")

        data = {}
        issues = []
        actions = []
        exec_logs = []
        verified_logs = []
        report = None

        # ── STAGE 1: INGEST ──────────────────────────────────────────
        logger.info(">> STAGE 1: INGESTION")
        try:
            if self.cb_manager:
                data = self.cb_manager.get("ingestion").call(self.ingestion.run)
            else:
                data = self.ingestion.run()
            self.latest_data = data
            total_records = sum(len(v) for v in data.values())
            logger.info(f"  [OK] Ingested {total_records} records")
        except Exception as e:
            logger.error(f"  [ERR] Ingestion failed: {e}")
            cycle.errors.append(f"Ingestion: {e}")
            data = {"procurement": [], "saas": [], "cloud": [], "sla": []}

        # ── STAGE 2: DETECT ──────────────────────────────────────────
        logger.info(">> STAGE 2: DETECTION")
        try:
            if self.cb_manager:
                issues = self.cb_manager.get("detection").call(self.detection.run, data)
            else:
                issues = self.detection.run(data)
            self.latest_issues = issues
            cycle.issues_detected = len(issues)
            logger.info(f"  [OK] Detected {len(issues)} inefficiencies")
            for issue in issues[:5]:
                logger.info(f"    - [{issue.severity.value.upper()}] {issue.title}")
        except Exception as e:
            logger.error(f"  [ERR] Detection failed: {e}")
            cycle.errors.append(f"Detection: {e}")

        # ── STAGE 3: DECIDE ──────────────────────────────────────────
        logger.info(">> STAGE 3: DECISION")
        try:
            if self.cb_manager:
                actions = self.cb_manager.get("decision").call(self.decision.run, issues)
            else:
                actions = self.decision.run(issues)
            self.latest_actions = actions
            logger.info(f"  [OK] Generated {len(actions)} action plans")
            for action in actions[:5]:
                logger.info(
                    f"    - {action.title} -> INR {action.estimated_savings_inr:,.0f} "
                    f"(conf={action.confidence_score:.0%}, risk={action.risk_score:.0%})"
                )
        except Exception as e:
            logger.error(f"  [ERR] Decision failed: {e}")
            cycle.errors.append(f"Decision: {e}")

        # ── SAFETY GATE ──────────────────────────────────────────────
        if self.safety and actions:
            safe_actions = []
            for action in actions:
                is_safe, reason = self.safety.check_action(action)
                if is_safe:
                    safe_actions.append(action)
                else:
                    logger.warning(f"  [BLOCKED] {action.title}: {reason}")
            if len(safe_actions) < len(actions):
                logger.info(f"  Safety: {len(actions) - len(safe_actions)} actions blocked")
            actions = safe_actions

        # ── STAGE 4: EXECUTE ─────────────────────────────────────────
        logger.info(">> STAGE 4: EXECUTION")
        try:
            self.execution.load_executed_keys(self._executed_keys)
            if self.cb_manager:
                exec_logs = self.cb_manager.get("execution").call(self.execution.run, actions)
            else:
                exec_logs = self.execution.run(actions)
            self._executed_keys = self.execution.get_executed_keys()
            executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
            cycle.actions_executed = executed
            logger.info(f"  [OK] Executed {executed}/{len(exec_logs)} actions")

            # Dead-letter queue for failed actions
            if self.state_db:
                for log in exec_logs:
                    if log.status.value == "failed":
                        self.state_db.add_to_dlq(
                            cycle_id, log.action_id,
                            json.dumps(log.request_payload),
                            log.error_message,
                        )
        except Exception as e:
            logger.error(f"  [ERR] Execution failed: {e}")
            cycle.errors.append(f"Execution: {e}")

        # ── STAGE 5: VERIFY ──────────────────────────────────────────
        logger.info(">> STAGE 5: VERIFICATION")
        try:
            if self.cb_manager:
                verified_logs = self.cb_manager.get("verification").call(
                    self.verification.run, actions, exec_logs
                )
            else:
                verified_logs = self.verification.run(actions, exec_logs)
            self.latest_executions = verified_logs
            verified_count = sum(1 for l in verified_logs if l.verified)
            logger.info(f"  [OK] Verified {verified_count}/{len(verified_logs)} executions")
        except Exception as e:
            logger.error(f"  [ERR] Verification failed: {e}")
            cycle.errors.append(f"Verification: {e}")
            verified_logs = exec_logs

        # ── STAGE 6: IMPACT ──────────────────────────────────────────
        logger.info(">> STAGE 6: IMPACT ANALYSIS")
        try:
            if self.cb_manager:
                report = self.cb_manager.get("impact").call(
                    self.impact.run, cycle_id, actions, verified_logs, issues
                )
            else:
                report = self.impact.run(cycle_id, actions, verified_logs, issues)
            self.latest_report = report
            cycle.total_savings_inr = report.total_impact_inr
            self._cumulative_savings += report.total_impact_inr
            logger.info(f"  [OK] Total impact: INR {report.total_impact_inr:,.0f}")
            logger.info(f"  [OK] Cumulative: INR {self._cumulative_savings:,.0f}")
        except Exception as e:
            logger.error(f"  [ERR] Impact failed: {e}")
            cycle.errors.append(f"Impact: {e}")

        # ── STAGE 7: AUDIT ──────────────────────────────────────────
        logger.info(">> STAGE 7: AUDIT LOGGING")
        try:
            log_path = self.audit.run(cycle_id, data, issues, actions, verified_logs, report)
            logger.info(f"  [OK] Audit log: {log_path}")
        except Exception as e:
            logger.error(f"  [ERR] Audit failed: {e}")
            cycle.errors.append(f"Audit: {e}")

        # ── METRICS ──────────────────────────────────────────────────
        if self.metrics_tracker and report:
            self.metrics_tracker.record_cycle(cycle_id, issues, actions, verified_logs, report)

        # ── PREDICTION ───────────────────────────────────────────────
        if self.predictor and self.state_db:
            try:
                history = self.state_db.get_savings_history()
                trend = self.predictor.predict_savings_trend(history)
                sla_data = data.get("sla", [])
                sla_risks = self.predictor.predict_sla_risks(sla_data) if sla_data else []
                saas_data = data.get("saas", [])
                cloud_data = data.get("cloud", [])
                leaks = self.predictor.predict_cost_leaks(saas_data, cloud_data)
                self.latest_predictions = {
                    "savings_trend": trend,
                    "sla_risks": sla_risks,
                    "cost_leaks": leaks[:10],
                }
                logger.info(f"  [OK] Predictions generated ({len(sla_risks)} SLA risks, {len(leaks)} leaks)")
            except Exception as e:
                logger.warning(f"  [WARN] Prediction failed: {e}")

        # ── SIMULATION ───────────────────────────────────────────────
        if self.simulation and actions and issues:
            try:
                self.latest_simulation = self.simulation.what_if("balanced", actions, issues)
                logger.info(f"  [OK] Simulation: {self.latest_simulation.get('filtered_count', 0)} strategies evaluated")
            except Exception as e:
                logger.warning(f"  [WARN] Simulation failed: {e}")

        # ── PERSIST STATE ────────────────────────────────────────────
        cycle.completed_at = datetime.utcnow()
        cycle.status = "completed" if not cycle.errors else "completed_with_errors"
        duration = (cycle.completed_at - cycle.started_at).total_seconds()

        if self.state_db:
            try:
                self.state_db.save_issues(cycle_id, issues)
                self.state_db.save_actions(cycle_id, actions)
                self.state_db.save_executions(cycle_id, verified_logs)
                if report:
                    self.state_db.save_impact(cycle_id, report)
                self.state_db.save_executed_keys(self._executed_keys)
                self.state_db.complete_cycle(
                    cycle_id, len(issues), cycle.actions_executed,
                    cycle.total_savings_inr, cycle.errors,
                )
            except Exception as e:
                logger.error(f"  [ERR] State persistence failed: {e}")

        logger.info(f"\n{'=' * 70}")
        logger.info(f"  CYCLE #{cycle_id} -- COMPLETED in {duration:.1f}s")
        logger.info(f"  Issues: {cycle.issues_detected} | Actions: {cycle.actions_executed}")
        logger.info(f"  Savings: INR {cycle.total_savings_inr:,.0f} | Errors: {len(cycle.errors)}")
        logger.info(f"  Cumulative: INR {self._cumulative_savings:,.0f}")
        logger.info(f"{'=' * 70}\n")

    # ── API-facing getters ───────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "cumulative_savings_inr": self._cumulative_savings,
            "start_time": datetime.utcnow().isoformat(),
        }
