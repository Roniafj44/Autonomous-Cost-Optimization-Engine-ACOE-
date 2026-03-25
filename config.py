"""
ACOE — Configuration Loader
YAML-based config with schema validation and dynamic overrides.
"""

from __future__ import annotations

import os
import logging
from typing import Any

import yaml

logger = logging.getLogger("acoe.config")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.yaml")

# ── Schema Definition ────────────────────────────────────────────────────────

CONFIG_SCHEMA = {
    "system": {"mode": str, "demo_mode": bool, "random_seed": int},
    "scheduler": {
        "interval_seconds": (int, float),
        "max_backoff_seconds": (int, float),
        "backoff_multiplier": (int, float),
        "max_consecutive_failures": int,
        "enable_partial_runs": bool,
    },
    "thresholds": {
        "saas_utilization_pct": (int, float),
        "cloud_utilization_pct": (int, float),
        "sla_breach_window_hours": (int, float),
        "anomaly_z_score": (int, float),
        "duplicate_vendor_similarity": (int, float),
    },
    "decision": {
        "min_confidence": (int, float),
        "max_risk": (int, float),
        "time_horizon_months": int,
        "roi_threshold": (int, float),
    },
    "execution": {
        "approval_gate": bool,
        "max_retries": int,
        "retry_backoff_base": (int, float),
        "idempotency_window_hours": (int, float),
    },
    "safety": {
        "max_actions_per_cycle": int,
        "budget_cap_inr_per_cycle": (int, float),
        "min_infra_utilization_pct": (int, float),
        "critical_services": list,
        "max_downgrade_pct": (int, float),
    },
    "circuit_breaker": {
        "failure_threshold": int,
        "recovery_timeout_seconds": (int, float),
        "half_open_max_calls": int,
    },
    "logging": {
        "level": str,
        "json_logs": bool,
        "console_logs": bool,
        "log_dir": str,
        "max_log_files": int,
    },
    "database": {"type": str, "path": str},
    "api": {"host": str, "port": int},
    "prediction": {
        "enabled": bool,
        "lookback_cycles": int,
        "forecast_horizon_months": int,
        "method": str,
    },
}


def _validate(cfg: dict, schema: dict, path: str = "") -> list[str]:
    """Validate config against schema, return list of errors."""
    errors = []
    for key, expected in schema.items():
        full_key = f"{path}.{key}" if path else key
        if key not in cfg:
            errors.append(f"Missing key: {full_key}")
            continue
        val = cfg[key]
        if isinstance(expected, dict):
            if not isinstance(val, dict):
                errors.append(f"{full_key}: expected dict, got {type(val).__name__}")
            else:
                errors.extend(_validate(val, expected, full_key))
        elif isinstance(expected, tuple):
            if not isinstance(val, expected):
                errors.append(f"{full_key}: expected {expected}, got {type(val).__name__}")
        elif not isinstance(val, expected):
            errors.append(f"{full_key}: expected {expected.__name__}, got {type(val).__name__}")
    return errors


class Config:
    """Thread-safe configuration with YAML loading, validation, and dynamic overrides."""

    _instance = None
    _data: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            errors = _validate(self._data, CONFIG_SCHEMA)
            if errors:
                for e in errors:
                    logger.warning(f"Config validation: {e}")
            logger.info(f"Configuration loaded from {CONFIG_FILE}")
        else:
            logger.warning(f"Config file not found: {CONFIG_FILE}, using defaults")
            self._data = {}

    def reload(self):
        """Reload config from YAML file."""
        self._load()

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Get a config value using dot notation: 'thresholds.saas_utilization_pct'"""
        keys = dotted_key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, dotted_key: str, value: Any):
        """Dynamic override of a config value."""
        keys = dotted_key.split(".")
        d = self._data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value

    def to_dict(self) -> dict:
        return dict(self._data)

    # ── Convenience properties ───────────────────────────────────────────

    @property
    def demo_mode(self) -> bool:
        return self.get("system.demo_mode", True)

    @property
    def loop_interval(self) -> float:
        return self.get("scheduler.interval_seconds", 60)

    @property
    def approval_gate(self) -> bool:
        return self.get("execution.approval_gate", False)

    @property
    def saas_threshold(self) -> float:
        return self.get("thresholds.saas_utilization_pct", 40) / 100.0

    @property
    def cloud_threshold(self) -> float:
        return self.get("thresholds.cloud_utilization_pct", 35) / 100.0

    @property
    def sla_breach_window(self) -> float:
        return self.get("thresholds.sla_breach_window_hours", 48)

    @property
    def anomaly_z_threshold(self) -> float:
        return self.get("thresholds.anomaly_z_score", 2.0)

    @property
    def min_confidence(self) -> float:
        return self.get("decision.min_confidence", 0.60)

    @property
    def max_risk(self) -> float:
        return self.get("decision.max_risk", 0.70)

    @property
    def time_horizon_months(self) -> int:
        return self.get("decision.time_horizon_months", 12)

    @property
    def max_retries(self) -> int:
        return self.get("execution.max_retries", 3)

    @property
    def retry_backoff_base(self) -> float:
        return self.get("execution.retry_backoff_base", 2.0)

    @property
    def db_path(self) -> str:
        return os.path.join(BASE_DIR, self.get("database.path", "state/acoe.db"))

    @property
    def log_dir(self) -> str:
        return os.path.join(BASE_DIR, self.get("logging.log_dir", "logs"))

    @property
    def api_host(self) -> str:
        return self.get("api.host", "0.0.0.0")

    @property
    def api_port(self) -> int:
        return self.get("api.port", 8000)

    @property
    def max_actions_per_cycle(self) -> int:
        return self.get("safety.max_actions_per_cycle", 50)

    @property
    def budget_cap(self) -> float:
        return self.get("safety.budget_cap_inr_per_cycle", 10000000)

    @property
    def critical_services(self) -> list:
        return self.get("safety.critical_services", [])

    @property
    def max_downgrade_pct(self) -> float:
        return self.get("safety.max_downgrade_pct", 80)

    @property
    def min_infra_utilization(self) -> float:
        return self.get("safety.min_infra_utilization_pct", 15) / 100.0

    @property
    def cb_failure_threshold(self) -> int:
        return self.get("circuit_breaker.failure_threshold", 3)

    @property
    def cb_recovery_timeout(self) -> float:
        return self.get("circuit_breaker.recovery_timeout_seconds", 120)


# Singleton accessor
def get_config() -> Config:
    return Config()


# ── Legacy compatibility shim ────────────────────────────────────────────────
# These module-level constants keep existing agents working during migration.

_cfg = get_config()

DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = _cfg.log_dir
STATE_DIR = os.path.join(BASE_DIR, "state")

LOOP_INTERVAL_SECONDS = _cfg.loop_interval
DEMO_MODE = _cfg.demo_mode
RANDOM_SEED = _cfg.get("system.random_seed", 42)

SAAS_UTILIZATION_THRESHOLD = _cfg.saas_threshold
CLOUD_UTILIZATION_THRESHOLD = _cfg.cloud_threshold
SLA_BREACH_WINDOW_HOURS = _cfg.sla_breach_window
ANOMALY_Z_SCORE_THRESHOLD = _cfg.anomaly_z_threshold
DUPLICATE_VENDOR_SIMILARITY = _cfg.get("thresholds.duplicate_vendor_similarity", 0.85)

MIN_CONFIDENCE_TO_ACT = _cfg.min_confidence
MAX_RISK_TO_ACT = _cfg.max_risk
DEFAULT_TIME_HORIZON_MONTHS = _cfg.time_horizon_months

APPROVAL_GATE_ENABLED = _cfg.approval_gate
MAX_RETRIES = _cfg.max_retries
RETRY_BACKOFF_BASE = _cfg.retry_backoff_base
IDEMPOTENCY_WINDOW_HOURS = _cfg.get("execution.idempotency_window_hours", 24)

API_HOST = _cfg.api_host
API_PORT = _cfg.api_port

CURRENCY_SYMBOL = "INR"
CURRENCY_LOCALE = "en_IN"

for d in [DATA_DIR, LOGS_DIR, STATE_DIR]:
    os.makedirs(d, exist_ok=True)
