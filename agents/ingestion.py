"""
ACOE — Ingestion Agent
Loads, validates, and normalizes enterprise data from CSV/JSON sources.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any

from models.schemas import (
    CloudUsage,
    ProcurementRecord,
    SaaSSubscription,
    SLAMetric,
)
import config

logger = logging.getLogger("acoe.ingestion")


class IngestionAgent:
    """Continuously ingest enterprise data from configured sources."""

    def __init__(self):
        self.data_dir = config.DATA_DIR
        self._stats = {"loaded": 0, "skipped": 0, "errors": []}

    # ── Public API ───────────────────────────────────────────────────────

    def run(self) -> dict[str, list]:
        """
        Execute full ingestion cycle.
        Returns dict with keys: procurement, saas, cloud, sla
        """
        logger.info("Ingestion Agent: starting data ingestion cycle")
        self._stats = {"loaded": 0, "skipped": 0, "errors": []}

        result = {
            "procurement": self._load_procurement(),
            "saas": self._load_saas(),
            "cloud": self._load_cloud(),
            "sla": self._load_sla(),
        }

        total = sum(len(v) for v in result.values())
        logger.info(
            f"Ingestion Agent: completed — {total} records loaded, "
            f"{self._stats['skipped']} skipped, "
            f"{len(self._stats['errors'])} errors"
        )
        return result

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── CSV Loaders ──────────────────────────────────────────────────────

    def _load_procurement(self) -> list[ProcurementRecord]:
        path = os.path.join(self.data_dir, "procurement.csv")
        rows = self._read_csv(path)
        records = []
        for row in rows:
            try:
                rec = ProcurementRecord(
                    record_id=row["record_id"],
                    vendor_name=row["vendor_name"],
                    service_category=row["service_category"],
                    contract_value_inr=float(row["contract_value_inr"]),
                    contract_start=datetime.fromisoformat(row["contract_start"]),
                    contract_end=datetime.fromisoformat(row["contract_end"]),
                    department=row["department"],
                    payment_frequency=row.get("payment_frequency", "monthly"),
                    description=row.get("description", ""),
                )
                records.append(rec)
                self._stats["loaded"] += 1
            except Exception as e:
                self._stats["skipped"] += 1
                self._stats["errors"].append(f"Procurement row error: {e}")
                logger.warning(f"Skipping procurement row: {e}")
        return records

    def _load_saas(self) -> list[SaaSSubscription]:
        path = os.path.join(self.data_dir, "saas_subscriptions.csv")
        rows = self._read_csv(path)
        records = []
        for row in rows:
            try:
                rec = SaaSSubscription(
                    subscription_id=row["subscription_id"],
                    vendor_name=row["vendor_name"],
                    product_name=row["product_name"],
                    total_licenses=int(row["total_licenses"]),
                    active_users=int(row["active_users"]),
                    monthly_cost_inr=float(row["monthly_cost_inr"]),
                    plan_tier=row.get("plan_tier", "standard"),
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
        path = os.path.join(self.data_dir, "cloud_usage.csv")
        rows = self._read_csv(path)
        records = []
        for row in rows:
            try:
                rec = CloudUsage(
                    resource_id=row["resource_id"],
                    provider=row["provider"],
                    resource_type=row["resource_type"],
                    region=row["region"],
                    capacity_units=float(row["capacity_units"]),
                    avg_usage_units=float(row["avg_usage_units"]),
                    peak_usage_units=float(row["peak_usage_units"]),
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
        path = os.path.join(self.data_dir, "sla_metrics.csv")
        rows = self._read_csv(path)
        records = []
        for row in rows:
            try:
                rec = SLAMetric(
                    sla_id=row["sla_id"],
                    service_name=row["service_name"],
                    vendor_name=row["vendor_name"],
                    metric_name=row["metric_name"],
                    target_value=float(row["target_value"]),
                    current_value=float(row["current_value"]),
                    measurement_unit=row["measurement_unit"],
                    breach_penalty_inr=float(row["breach_penalty_inr"]),
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

    # ── Helpers ───────────────────────────────────────────────────────────

    def _read_csv(self, path: str) -> list[dict[str, Any]]:
        if not os.path.exists(path):
            logger.error(f"Data file not found: {path}")
            self._stats["errors"].append(f"File not found: {path}")
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            self._stats["errors"].append(f"Read error: {path} — {e}")
            return []
