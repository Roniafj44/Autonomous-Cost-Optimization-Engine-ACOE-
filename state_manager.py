"""
ACOE -- SQLite State Manager
Persistent state across runs: issues history, action history, impact logs.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("acoe.state")


class StateManager:
    """SQLite-backed persistent state with versioned records and idempotency."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cycles (
                cycle_id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'running',
                issues_detected INTEGER DEFAULT 0,
                actions_executed INTEGER DEFAULT 0,
                total_savings REAL DEFAULT 0.0,
                errors TEXT DEFAULT '[]',
                version INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                issue_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                affected_entity_id TEXT,
                potential_savings REAL DEFAULT 0.0,
                evidence TEXT DEFAULT '{}',
                detected_at TEXT NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(cycle_id)
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                action_id TEXT NOT NULL UNIQUE,
                issue_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                title TEXT NOT NULL,
                target_entity_id TEXT,
                estimated_savings REAL DEFAULT 0.0,
                roi_estimate REAL DEFAULT 0.0,
                risk_score REAL DEFAULT 0.0,
                confidence_score REAL DEFAULT 0.0,
                justification TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(cycle_id)
            );

            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                execution_id TEXT NOT NULL UNIQUE,
                action_id TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0,
                verification_notes TEXT,
                request_payload TEXT DEFAULT '{}',
                response_payload TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                executed_at TEXT NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(cycle_id)
            );

            CREATE TABLE IF NOT EXISTS impact_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL UNIQUE,
                report_id TEXT NOT NULL,
                realized_savings REAL DEFAULT 0.0,
                projected_savings REAL DEFAULT 0.0,
                avoided_penalties REAL DEFAULT 0.0,
                total_impact REAL DEFAULT 0.0,
                breakdown TEXT DEFAULT '[]',
                summary TEXT DEFAULT '',
                generated_at TEXT NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES cycles(cycle_id)
            );

            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER,
                action_id TEXT NOT NULL,
                action_data TEXT NOT NULL,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                recorded_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_issues_cycle ON issues(cycle_id);
            CREATE INDEX IF NOT EXISTS idx_actions_cycle ON actions(cycle_id);
            CREATE INDEX IF NOT EXISTS idx_executions_cycle ON executions(cycle_id);
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
        """)
        conn.commit()

    # ── Cycle Management ─────────────────────────────────────────────────

    def start_cycle(self, cycle_id: int) -> int:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cycles (cycle_id, started_at, status) VALUES (?, ?, ?)",
            (cycle_id, datetime.utcnow().isoformat(), "running"),
        )
        conn.commit()
        return cycle_id

    def complete_cycle(self, cycle_id: int, issues: int, actions: int,
                       savings: float, errors: list):
        conn = self._get_conn()
        conn.execute(
            """UPDATE cycles SET completed_at=?, status=?, issues_detected=?,
               actions_executed=?, total_savings=?, errors=? WHERE cycle_id=?""",
            (datetime.utcnow().isoformat(),
             "completed" if not errors else "completed_with_errors",
             issues, actions, savings, json.dumps(errors), cycle_id),
        )
        conn.commit()

    def get_cycle_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT MAX(cycle_id) FROM cycles").fetchone()
        return row[0] or 0

    # ── Issue Storage ────────────────────────────────────────────────────

    def save_issues(self, cycle_id: int, issues: list):
        conn = self._get_conn()
        for issue in issues:
            conn.execute(
                """INSERT INTO issues (cycle_id, issue_id, category, severity, title,
                   description, affected_entity_id, potential_savings, evidence, detected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cycle_id, issue.issue_id, issue.category.value, issue.severity.value,
                 issue.title, issue.description, issue.affected_entity_id,
                 issue.potential_savings_inr, json.dumps(issue.evidence),
                 issue.detected_at.isoformat()),
            )
        conn.commit()

    def get_issues_history(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM issues ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Action Storage ───────────────────────────────────────────────────

    def save_actions(self, cycle_id: int, actions: list):
        conn = self._get_conn()
        for action in actions:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO actions (cycle_id, action_id, issue_id,
                       action_type, title, target_entity_id, estimated_savings,
                       roi_estimate, risk_score, confidence_score, justification,
                       status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cycle_id, action.action_id, action.issue_id,
                     action.action_type.value, action.title, action.target_entity_id,
                     action.estimated_savings_inr, action.roi_estimate,
                     action.risk_score, action.confidence_score, action.justification,
                     action.status.value, action.created_at.isoformat()),
                )
            except Exception as e:
                logger.warning(f"Duplicate action skipped: {action.action_id}")
        conn.commit()

    # ── Execution Storage ────────────────────────────────────────────────

    def save_executions(self, cycle_id: int, logs: list):
        conn = self._get_conn()
        for log in logs:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO executions (cycle_id, execution_id, action_id,
                       status, attempts, verified, verification_notes, request_payload,
                       response_payload, error_message, executed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cycle_id, log.execution_id, log.action_id, log.status.value,
                     log.attempts, 1 if log.verified else 0, log.verification_notes,
                     json.dumps(log.request_payload), json.dumps(log.response_payload),
                     log.error_message, log.executed_at.isoformat()),
                )
            except Exception as e:
                logger.warning(f"Duplicate execution skipped: {log.execution_id}")
        conn.commit()

    # ── Impact Storage ───────────────────────────────────────────────────

    def save_impact(self, cycle_id: int, report):
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO impact_reports (cycle_id, report_id,
               realized_savings, projected_savings, avoided_penalties,
               total_impact, breakdown, summary, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cycle_id, report.report_id, report.realized_savings_inr,
             report.projected_annual_savings_inr, report.avoided_penalties_inr,
             report.total_impact_inr, json.dumps(report.breakdown),
             report.summary, report.generated_at.isoformat()),
        )
        conn.commit()

    # ── Idempotency Keys ─────────────────────────────────────────────────

    def get_executed_keys(self) -> list[str]:
        conn = self._get_conn()
        val = conn.execute(
            "SELECT value FROM system_state WHERE key='executed_keys'"
        ).fetchone()
        if val:
            return json.loads(val[0])
        return []

    def save_executed_keys(self, keys: list[str]):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("executed_keys", json.dumps(keys), datetime.utcnow().isoformat()),
        )
        conn.commit()

    # ── Cumulative Savings ───────────────────────────────────────────────

    def get_cumulative_savings(self) -> float:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(total_savings), 0) FROM cycles"
        ).fetchone()
        return row[0]

    # ── Dead Letter Queue ─────────────────────────────────────────────────

    def add_to_dlq(self, cycle_id: int, action_id: str, action_data: str,
                   error: str):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO dead_letter_queue (cycle_id, action_id, action_data,
               error_message, created_at) VALUES (?, ?, ?, ?, ?)""",
            (cycle_id, action_id, action_data, error, datetime.utcnow().isoformat()),
        )
        conn.commit()

    def get_dlq_items(self, status: str = "pending") -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM dead_letter_queue WHERE status=? ORDER BY id",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_dlq_status(self, item_id: int, status: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE dead_letter_queue SET status=? WHERE id=?", (status, item_id)
        )
        conn.commit()

    # ── Metrics ──────────────────────────────────────────────────────────

    def save_metric(self, cycle_id: int, name: str, value: float):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO metrics (cycle_id, metric_name, metric_value, recorded_at) VALUES (?, ?, ?, ?)",
            (cycle_id, name, value, datetime.utcnow().isoformat()),
        )
        conn.commit()

    def get_metric_history(self, name: str, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT cycle_id, metric_value, recorded_at FROM metrics WHERE metric_name=? ORDER BY id DESC LIMIT ?",
            (name, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_metrics_latest(self) -> dict:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT metric_name, metric_value FROM metrics
               WHERE id IN (SELECT MAX(id) FROM metrics GROUP BY metric_name)"""
        ).fetchall()
        return {r["metric_name"]: r["metric_value"] for r in rows}

    # ── Savings History for Prediction ───────────────────────────────────

    def get_savings_history(self, limit: int = 20) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT cycle_id, total_savings, issues_detected, actions_executed,
               completed_at FROM cycles WHERE status LIKE 'completed%'
               ORDER BY cycle_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
