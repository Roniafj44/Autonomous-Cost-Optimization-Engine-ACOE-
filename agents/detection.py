"""
ACOE — Detection Agent
Rule-based heuristics + statistical anomaly detection for cost inefficiencies.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime

import numpy as np

from models.schemas import (
    CloudUsage,
    DetectedIssue,
    IssueCategory,
    IssueSeverity,
    ProcurementRecord,
    SaaSSubscription,
    SLAMetric,
)
import config

logger = logging.getLogger("acoe.detection")


class DetectionAgent:
    """Detect inefficiencies using rule-based + statistical methods."""

    def run(self, data: dict[str, list]) -> list[DetectedIssue]:
        """
        Analyze ingested data and return list of detected issues.
        """
        logger.info("Detection Agent: starting analysis")
        issues: list[DetectedIssue] = []

        issues.extend(self._detect_duplicate_vendors(data.get("procurement", [])))
        issues.extend(self._detect_saas_underutilization(data.get("saas", [])))
        issues.extend(self._detect_cloud_overprovisioning(data.get("cloud", [])))
        issues.extend(self._detect_sla_breach_risk(data.get("sla", [])))
        issues.extend(self._detect_cost_anomalies(data))

        logger.info(f"Detection Agent: found {len(issues)} issues")
        return issues

    # ── 1. Duplicate Vendor Detection ────────────────────────────────────

    def _detect_duplicate_vendors(
        self, records: list[ProcurementRecord]
    ) -> list[DetectedIssue]:
        issues = []
        # Group by service_category
        by_category: dict[str, list[ProcurementRecord]] = defaultdict(list)
        for rec in records:
            by_category[rec.service_category.lower().strip()].append(rec)

        for category, vendors in by_category.items():
            if len(vendors) > 1:
                # Multiple vendors in same category = potential duplicate
                vendor_names = [v.vendor_name for v in vendors]
                total_cost = sum(v.contract_value_inr for v in vendors)
                min_cost = min(v.contract_value_inr for v in vendors)
                potential_savings = total_cost - min_cost  # consolidate to cheapest

                severity = IssueSeverity.HIGH if potential_savings > 1000000 else IssueSeverity.MEDIUM

                issues.append(
                    DetectedIssue(
                        issue_id=f"DUP-{uuid.uuid4().hex[:8].upper()}",
                        category=IssueCategory.DUPLICATE_VENDOR,
                        severity=severity,
                        title=f"Duplicate vendors in {category}",
                        description=(
                            f"Found {len(vendors)} vendors providing {category}: "
                            f"{', '.join(vendor_names)}. "
                            f"Consolidation could save ₹{potential_savings:,.0f}/year."
                        ),
                        affected_entity_id=vendors[0].record_id,
                        affected_entity_type="procurement",
                        evidence={
                            "category": category,
                            "vendors": [
                                {"name": v.vendor_name, "cost": v.contract_value_inr, "id": v.record_id}
                                for v in vendors
                            ],
                            "total_cost": total_cost,
                        },
                        potential_savings_inr=potential_savings,
                    )
                )
        return issues

    # ── 2. SaaS Underutilization ─────────────────────────────────────────

    def _detect_saas_underutilization(
        self, subscriptions: list[SaaSSubscription]
    ) -> list[DetectedIssue]:
        issues = []
        threshold = config.SAAS_UTILIZATION_THRESHOLD

        for sub in subscriptions:
            ratio = sub.utilization_ratio
            if ratio < threshold:
                unused_licenses = sub.total_licenses - sub.active_users
                cost_per_license = (
                    sub.monthly_cost_inr / sub.total_licenses
                    if sub.total_licenses > 0
                    else 0
                )
                monthly_waste = unused_licenses * cost_per_license
                annual_savings = monthly_waste * 12

                severity = IssueSeverity.CRITICAL if ratio < 0.20 else (
                    IssueSeverity.HIGH if ratio < 0.30 else IssueSeverity.MEDIUM
                )

                issues.append(
                    DetectedIssue(
                        issue_id=f"SAAS-{uuid.uuid4().hex[:8].upper()}",
                        category=IssueCategory.SAAS_UNDERUTILIZATION,
                        severity=severity,
                        title=f"{sub.product_name} underutilized ({ratio:.0%})",
                        description=(
                            f"{sub.product_name} by {sub.vendor_name}: "
                            f"{sub.active_users}/{sub.total_licenses} licenses used "
                            f"({ratio:.1%} utilization). "
                            f"{unused_licenses} unused licenses = ₹{annual_savings:,.0f}/year wasted."
                        ),
                        affected_entity_id=sub.subscription_id,
                        affected_entity_type="saas_subscription",
                        evidence={
                            "product": sub.product_name,
                            "vendor": sub.vendor_name,
                            "total_licenses": sub.total_licenses,
                            "active_users": sub.active_users,
                            "utilization": round(ratio, 4),
                            "monthly_cost": sub.monthly_cost_inr,
                            "unused_licenses": unused_licenses,
                        },
                        potential_savings_inr=annual_savings,
                    )
                )
        return issues

    # ── 3. Cloud Over-provisioning ───────────────────────────────────────

    def _detect_cloud_overprovisioning(
        self, resources: list[CloudUsage]
    ) -> list[DetectedIssue]:
        issues = []
        threshold = config.CLOUD_UTILIZATION_THRESHOLD

        for res in resources:
            ratio = res.utilization_ratio
            if ratio < threshold:
                # Savings = cost proportional to unused capacity
                right_size_factor = max(res.peak_usage_units / res.capacity_units, 0.2)
                potential_savings = res.monthly_cost_inr * (1 - right_size_factor) * 12

                severity = IssueSeverity.HIGH if ratio < 0.20 else IssueSeverity.MEDIUM

                issues.append(
                    DetectedIssue(
                        issue_id=f"CLD-{uuid.uuid4().hex[:8].upper()}",
                        category=IssueCategory.CLOUD_OVER_PROVISIONING,
                        severity=severity,
                        title=f"{res.resource_type} on {res.provider} over-provisioned ({ratio:.0%})",
                        description=(
                            f"{res.resource_id} ({res.resource_type}) on {res.provider}: "
                            f"avg usage {res.avg_usage_units}/{res.capacity_units} units "
                            f"({ratio:.1%}). Right-sizing could save ₹{potential_savings:,.0f}/year."
                        ),
                        affected_entity_id=res.resource_id,
                        affected_entity_type="cloud_resource",
                        evidence={
                            "provider": res.provider,
                            "resource_type": res.resource_type,
                            "capacity": res.capacity_units,
                            "avg_usage": res.avg_usage_units,
                            "peak_usage": res.peak_usage_units,
                            "utilization": round(ratio, 4),
                            "monthly_cost": res.monthly_cost_inr,
                        },
                        potential_savings_inr=potential_savings,
                    )
                )
        return issues

    # ── 4. SLA Breach Risk ───────────────────────────────────────────────

    def _detect_sla_breach_risk(
        self, metrics: list[SLAMetric]
    ) -> list[DetectedIssue]:
        issues = []
        window_hours = config.SLA_BREACH_WINDOW_HOURS

        for sla in metrics:
            hours_left = sla.hours_to_breach

            # Check if metric is trending toward breach
            is_underperforming = False
            if sla.measurement_unit == "percent":
                is_underperforming = sla.current_value < sla.target_value
            elif sla.measurement_unit in ("milliseconds", "minutes"):
                is_underperforming = sla.current_value > sla.target_value
            elif sla.measurement_unit == "requests_per_sec":
                is_underperforming = sla.current_value < sla.target_value

            if hours_left < window_hours and is_underperforming:
                severity = IssueSeverity.CRITICAL if hours_left < 24 else IssueSeverity.HIGH

                issues.append(
                    DetectedIssue(
                        issue_id=f"SLA-{uuid.uuid4().hex[:8].upper()}",
                        category=IssueCategory.SLA_BREACH_RISK,
                        severity=severity,
                        title=f"SLA breach risk: {sla.service_name} ({hours_left:.0f}h remaining)",
                        description=(
                            f"{sla.service_name} ({sla.metric_name}): "
                            f"current={sla.current_value} vs target={sla.target_value} "
                            f"({sla.measurement_unit}). "
                            f"Breach in {hours_left:.0f}h. "
                            f"Penalty at risk: ₹{sla.breach_penalty_inr:,.0f}."
                        ),
                        affected_entity_id=sla.sla_id,
                        affected_entity_type="sla_metric",
                        evidence={
                            "service": sla.service_name,
                            "vendor": sla.vendor_name,
                            "metric": sla.metric_name,
                            "target": sla.target_value,
                            "current": sla.current_value,
                            "hours_to_breach": round(hours_left, 1),
                            "penalty_inr": sla.breach_penalty_inr,
                        },
                        potential_savings_inr=sla.breach_penalty_inr,
                    )
                )
        return issues

    # ── 5. Statistical Cost Anomaly Detection ────────────────────────────

    def _detect_cost_anomalies(self, data: dict[str, list]) -> list[DetectedIssue]:
        """Z-score based anomaly detection on cost fields."""
        issues = []
        z_threshold = config.ANOMALY_Z_SCORE_THRESHOLD

        # Check SaaS cost anomalies
        saas_list: list[SaaSSubscription] = data.get("saas", [])
        if len(saas_list) > 3:
            costs = np.array([s.monthly_cost_inr for s in saas_list])
            mean_cost = np.mean(costs)
            std_cost = np.std(costs)
            if std_cost > 0:
                for i, sub in enumerate(saas_list):
                    z = (sub.monthly_cost_inr - mean_cost) / std_cost
                    if z > z_threshold:
                        issues.append(
                            DetectedIssue(
                                issue_id=f"ANM-{uuid.uuid4().hex[:8].upper()}",
                                category=IssueCategory.COST_ANOMALY,
                                severity=IssueSeverity.MEDIUM,
                                title=f"Cost anomaly: {sub.product_name} (z={z:.1f})",
                                description=(
                                    f"{sub.product_name} monthly cost ₹{sub.monthly_cost_inr:,.0f} "
                                    f"is {z:.1f} standard deviations above mean (₹{mean_cost:,.0f}). "
                                    f"Review for potential renegotiation."
                                ),
                                affected_entity_id=sub.subscription_id,
                                affected_entity_type="saas_subscription",
                                evidence={
                                    "cost": sub.monthly_cost_inr,
                                    "mean": round(mean_cost, 2),
                                    "std": round(std_cost, 2),
                                    "z_score": round(z, 3),
                                },
                                potential_savings_inr=(sub.monthly_cost_inr - mean_cost) * 12,
                            )
                        )

        # Check cloud cost anomalies
        cloud_list: list[CloudUsage] = data.get("cloud", [])
        if len(cloud_list) > 3:
            costs = np.array([c.monthly_cost_inr for c in cloud_list])
            mean_cost = np.mean(costs)
            std_cost = np.std(costs)
            if std_cost > 0:
                for res in cloud_list:
                    z = (res.monthly_cost_inr - mean_cost) / std_cost
                    if z > z_threshold:
                        issues.append(
                            DetectedIssue(
                                issue_id=f"ANM-{uuid.uuid4().hex[:8].upper()}",
                                category=IssueCategory.COST_ANOMALY,
                                severity=IssueSeverity.MEDIUM,
                                title=f"Cost anomaly: {res.resource_type} on {res.provider} (z={z:.1f})",
                                description=(
                                    f"{res.resource_id} monthly cost ₹{res.monthly_cost_inr:,.0f} "
                                    f"is {z:.1f}σ above mean (₹{mean_cost:,.0f})."
                                ),
                                affected_entity_id=res.resource_id,
                                affected_entity_type="cloud_resource",
                                evidence={
                                    "cost": res.monthly_cost_inr,
                                    "mean": round(mean_cost, 2),
                                    "std": round(std_cost, 2),
                                    "z_score": round(z, 3),
                                },
                                potential_savings_inr=(res.monthly_cost_inr - mean_cost) * 12,
                            )
                        )

        return issues
