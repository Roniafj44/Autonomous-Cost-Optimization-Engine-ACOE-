"""
ACOE — Ingestion Agent (Stage 1 of 7)
Loads, validates, and normalizes enterprise data from CSV/JSON sources.

★ HOW IT WORKS:
  - Reads 4 CSV files from the data/ directory
  - Validates each row against the Pydantic schema (models/schemas.py)
  - Returns a dictionary with 4 lists of typed Python objects
  - Invalid or malformed rows are skipped with a warning (not a crash)

★ WHAT IT READS:
  - data/procurement.csv         → list[ProcurementRecord]
  - data/saas_subscriptions.csv  → list[SaaSSubscription]
  - data/cloud_usage.csv         → list[CloudUsage]
  - data/sla_metrics.csv         → list[SLAMetric]

★ HOW TO PLUG IN YOUR OWN DATA:
  Option A: Replace the CSV files in data/ directly
  Option B: Upload via the Streamlit dashboard — it monkey-patches this agent
            to redirect file reads to your uploaded temp files (see dashboard/app.py)
"""

from __future__ import annotations

import csv      # Standard library CSV reader
import json     # Standard library JSON parser
import logging  # Standard library logger
import os       # For file path operations
from datetime import datetime  # For parsing date strings into datetime objects
from typing import Any         # For generic type hints

# ── Import the Pydantic data models ──────────────────────────────────────────
# These define the expected schema (column names, types) for each data source
# Located in: models/schemas.py
from models.schemas import (
    CloudUsage,           # Cloud resource record schema
    ProcurementRecord,    # Procurement contract schema
    SaaSSubscription,     # SaaS subscription schema
    SLAMetric,            # SLA metrics schema
)

import config  # Loads DATA_DIR path from config.yaml

# ── Logger setup ─────────────────────────────────────────────────────────────
# Uses Python's built-in logging module; output level controlled by config.yaml
logger = logging.getLogger("acoe.ingestion")


class IngestionAgent:
    """
    Stage 1: Continuously ingest enterprise data from configured sources.

    This agent is instantiated fresh each pipeline cycle to ensure
    it always reads the latest file contents (no caching).
    """

    def __init__(self):
        # DATA_DIR is set in config.py → points to the data/ folder
        self.data_dir = config.DATA_DIR

        # Track loading stats: how many rows loaded, skipped, and any errors
        self._stats = {"loaded": 0, "skipped": 0, "errors": []}

    # ── Public API ───────────────────────────────────────────────────────────

    def run(self) -> dict[str, list]:
        """
        Execute the full data ingestion cycle.

        Returns a dictionary with 4 keys:
          {
            "procurement": [ProcurementRecord, ...],
            "saas":        [SaaSSubscription, ...],
            "cloud":       [CloudUsage, ...],
            "sla":         [SLAMetric, ...]
          }
        """
        logger.info("Ingestion Agent: starting data ingestion cycle")

        # Reset stats at the start of each cycle
        self._stats = {"loaded": 0, "skipped": 0, "errors": []}

        # Load each data source independently
        # If one file fails, the others still load (graceful degradation)
        result = {
            "procurement": self._load_procurement(),  # Reads procurement.csv
            "saas": self._load_saas(),                 # Reads saas_subscriptions.csv
            "cloud": self._load_cloud(),               # Reads cloud_usage.csv
            "sla": self._load_sla(),                   # Reads sla_metrics.csv
        }

        # Log summary of what was loaded
        total = sum(len(v) for v in result.values())
        logger.info(
            f"Ingestion Agent: completed — {total} records loaded, "
            f"{self._stats['skipped']} skipped, "
            f"{len(self._stats['errors'])} errors"
        )
        return result

    def get_stats(self) -> dict:
        """Return the loading statistics from the last run() call."""
        return dict(self._stats)

    # ── CSV Loaders ──────────────────────────────────────────────────────────
    # Each loader reads one CSV file and converts rows to typed Python objects.
    # Errors in a single row are caught and logged — bad rows are skipped.

    def _load_procurement(self) -> list[ProcurementRecord]:
        """
        Load procurement.csv → list of ProcurementRecord objects.

        Required columns:
          record_id, vendor_name, service_category, contract_value_inr,
          contract_start, contract_end, department, payment_frequency, description
        """
        path = os.path.join(self.data_dir, "procurement.csv")  # Full file path
        rows = self._read_csv(path)    # Get list of raw dict rows
        records = []

        for row in rows:
            try:
                # Convert raw CSV row (all strings) to a typed ProcurementRecord
                rec = ProcurementRecord(
                    record_id=row["record_id"],
                    vendor_name=row["vendor_name"],
                    service_category=row["service_category"],
                    contract_value_inr=float(row["contract_value_inr"]),    # String → float
                    contract_start=datetime.fromisoformat(row["contract_start"]),  # String → datetime
                    contract_end=datetime.fromisoformat(row["contract_end"]),
                    department=row["department"],
                    payment_frequency=row.get("payment_frequency", "monthly"),  # Optional column
                    description=row.get("description", ""),                      # Optional column
                )
                records.append(rec)
                self._stats["loaded"] += 1  # Count successful loads

            except Exception as e:
                # If a row has missing/malformed data, skip it and log a warning
                self._stats["skipped"] += 1
                self._stats["errors"].append(f"Procurement row error: {e}")
                logger.warning(f"Skipping procurement row: {e}")

        return records

    def _load_saas(self) -> list[SaaSSubscription]:
        """
        Load saas_subscriptions.csv → list of SaaSSubscription objects.

        Required columns:
          subscription_id, vendor_name, product_name, total_licenses,
          active_users, monthly_cost_inr, plan_tier, renewal_date, department

        The detection engine compares active_users / total_licenses to detect waste.
        """
        path = os.path.join(self.data_dir, "saas_subscriptions.csv")
        rows = self._read_csv(path)
        records = []

        for row in rows:
            try:
                rec = SaaSSubscription(
                    subscription_id=row["subscription_id"],
                    vendor_name=row["vendor_name"],
                    product_name=row["product_name"],
                    total_licenses=int(row["total_licenses"]),    # String → int
                    active_users=int(row["active_users"]),         # String → int
                    monthly_cost_inr=float(row["monthly_cost_inr"]),
                    plan_tier=row.get("plan_tier", "standard"),   # Optional, defaults to "standard"
                    renewal_date=datetime.fromisoformat(row["renewal_date"]),
                    department=row["department"],
                )
                records.append(rec)
                self._stats["loaded"] += 1

            except Exception as e:
                self._stats["skipped"] += 1
                self._stats["errors"].append(f"SaaS row error: {e}")
                logger.warning(f"Skipping SaaS row: {e}")

        return records

    def _load_cloud(self) -> list[CloudUsage]:
        """
        Load cloud_usage.csv → list of CloudUsage objects.

        Required columns:
          resource_id, provider, resource_type, region, capacity_units,
          avg_usage_units, peak_usage_units, monthly_cost_inr, department

        The detection engine compares avg_usage_units / capacity_units
        to find over-provisioned (wasteful) cloud resources.
        """
        path = os.path.join(self.data_dir, "cloud_usage.csv")
        rows = self._read_csv(path)
        records = []

        for row in rows:
            try:
                rec = CloudUsage(
                    resource_id=row["resource_id"],
                    provider=row["provider"],              # AWS | Azure | GCP
                    resource_type=row["resource_type"],    # EC2 | RDS | S3 etc.
                    region=row["region"],
                    capacity_units=float(row["capacity_units"]),     # Provisioned capacity
                    avg_usage_units=float(row["avg_usage_units"]),   # Average actual usage
                    peak_usage_units=float(row["peak_usage_units"]), # Peak usage (safety check)
                    monthly_cost_inr=float(row["monthly_cost_inr"]),
                    department=row["department"],
                )
                records.append(rec)
                self._stats["loaded"] += 1

            except Exception as e:
                self._stats["skipped"] += 1
                self._stats["errors"].append(f"Cloud row error: {e}")
                logger.warning(f"Skipping cloud row: {e}")

        return records

    def _load_sla(self) -> list[SLAMetric]:
        """
        Load sla_metrics.csv → list of SLAMetric objects.

        Required columns:
          sla_id, service_name, vendor_name, metric_name, target_value,
          current_value, measurement_unit, breach_penalty_inr,
          measurement_timestamp, breach_deadline

        The detection engine compares current_value to target_value
        and checks if breach_deadline is imminent (within 48 hours by default).
        """
        path = os.path.join(self.data_dir, "sla_metrics.csv")
        rows = self._read_csv(path)
        records = []

        for row in rows:
            try:
                rec = SLAMetric(
                    sla_id=row["sla_id"],
                    service_name=row["service_name"],
                    vendor_name=row["vendor_name"],
                    metric_name=row["metric_name"],                       # e.g. "uptime_pct"
                    target_value=float(row["target_value"]),              # SLA commitment (e.g. 99.9)
                    current_value=float(row["current_value"]),            # Actual measured value
                    measurement_unit=row["measurement_unit"],             # e.g. "percent"
                    breach_penalty_inr=float(row["breach_penalty_inr"]), # Financial penalty if breached
                    measurement_timestamp=datetime.fromisoformat(
                        row["measurement_timestamp"]
                    ),
                    breach_deadline=datetime.fromisoformat(row["breach_deadline"]),
                )
                records.append(rec)
                self._stats["loaded"] += 1

            except Exception as e:
                self._stats["skipped"] += 1
                self._stats["errors"].append(f"SLA row error: {e}")
                logger.warning(f"Skipping SLA row: {e}")

        return records

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_csv(self, path: str) -> list[dict[str, Any]]:
        """
        Read a CSV file and return a list of row dictionaries.

        Uses Python's csv.DictReader so each row is a dict
        mapping column_name → value (all values are strings).

        Returns an empty list if the file doesn't exist or can't be read.
        NOTE: The dashboard monkey-patches this method to redirect reads
              to uploaded temp files. See dashboard/app.py → _patch_ingestion_agent()
        """
        # Check if file exists before trying to read it
        if not os.path.exists(path):
            logger.error(f"Data file not found: {path}")
            self._stats["errors"].append(f"File not found: {path}")
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)   # Reads header row automatically as keys
                return list(reader)           # Convert generator to list of dicts
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            self._stats["errors"].append(f"Read error: {path} — {e}")
            return []
