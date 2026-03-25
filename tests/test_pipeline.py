"""
ACOE -- Unit & Integration Tests
Deterministic, reproducible tests for detection, impact, decision, and full pipeline.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from models.schemas import (
    ProcurementRecord, SaaSSubscription, CloudUsage, SLAMetric,
    DetectedIssue, ActionPlan, ExecutionLog, IssueCategory, IssueSeverity,
    ActionType, ActionStatus,
)
from agents.detection import DetectionAgent
from agents.decision import DecisionAgent
from agents.impact import ImpactAgent
from agents.ingestion import IngestionAgent
from agents.execution import ExecutionAgent
from agents.verification import VerificationAgent


class TestDetectionAgent(unittest.TestCase):
    """Unit tests for DetectionAgent."""

    def setUp(self):
        self.agent = DetectionAgent()

    def test_duplicate_vendor_detection(self):
        """Should detect duplicate vendors in same category."""
        now = datetime.utcnow()
        records = [
            ProcurementRecord(
                record_id="PO-001", vendor_name="VendorA",
                service_category="IT Consulting", contract_value_inr=500000,
                contract_start=now, contract_end=now + timedelta(days=365),
                department="IT",
            ),
            ProcurementRecord(
                record_id="PO-002", vendor_name="VendorB",
                service_category="IT Consulting", contract_value_inr=600000,
                contract_start=now, contract_end=now + timedelta(days=365),
                department="IT",
            ),
        ]
        data = {"procurement": records, "saas": [], "cloud": [], "sla": []}
        issues = self.agent.run(data)
        dup_issues = [i for i in issues if i.category == IssueCategory.DUPLICATE_VENDOR]
        self.assertGreater(len(dup_issues), 0, "Should detect duplicate vendors")
        self.assertIn(dup_issues[0].severity, [IssueSeverity.HIGH, IssueSeverity.MEDIUM])

    def test_saas_underutilization(self):
        """Should flag underutilized SaaS subscriptions."""
        subs = [
            SaaSSubscription(
                subscription_id="SUB-001", product_name="TestTool",
                vendor_name="TestVendor", plan_tier="enterprise",
                monthly_cost_inr=100000, total_licenses=100,
                active_users=15, renewal_date=datetime.utcnow() + timedelta(days=180),
                department="Engineering",
            ),
        ]
        data = {"procurement": [], "saas": subs, "cloud": [], "sla": []}
        issues = self.agent.run(data)
        under_issues = [i for i in issues if i.category == IssueCategory.SAAS_UNDERUTILIZATION]
        self.assertGreater(len(under_issues), 0, "Should flag underutilized SaaS")

    def test_cloud_overprovisioning(self):
        """Should detect cloud resources with low utilization."""
        resources = [
            CloudUsage(
                resource_id="R-001", provider="AWS", resource_type="EC2",
                region="us-east-1", capacity_units=100,
                avg_usage_units=10, peak_usage_units=25,
                monthly_cost_inr=200000, department="Engineering",
            ),
        ]
        data = {"procurement": [], "saas": [], "cloud": resources, "sla": []}
        issues = self.agent.run(data)
        cloud_issues = [i for i in issues if i.category == IssueCategory.CLOUD_OVER_PROVISIONING]
        self.assertGreater(len(cloud_issues), 0, "Should detect overprovisioned cloud")

    def test_sla_breach_risk(self):
        """Should detect SLAs approaching breach."""
        now = datetime.utcnow()
        slas = [
            SLAMetric(
                sla_id="SLA-001", service_name="TestService", vendor_name="TestVendor",
                metric_name="uptime", target_value=99.9, current_value=98.5,
                measurement_unit="percent", breach_penalty_inr=500000,
                measurement_timestamp=now,
                breach_deadline=now + timedelta(hours=12),
            ),
        ]
        data = {"procurement": [], "saas": [], "cloud": [], "sla": slas}
        issues = self.agent.run(data)
        sla_issues = [i for i in issues if i.category == IssueCategory.SLA_BREACH_RISK]
        self.assertGreater(len(sla_issues), 0, "Should detect SLA breach risk")

    def test_no_false_positives(self):
        """Empty data should produce no issues."""
        data = {"procurement": [], "saas": [], "cloud": [], "sla": []}
        issues = self.agent.run(data)
        self.assertEqual(len(issues), 0, "Empty data should produce no issues")


class TestDecisionAgent(unittest.TestCase):
    """Unit tests for DecisionAgent."""

    def setUp(self):
        self.agent = DecisionAgent()

    def test_generates_action_for_issue(self):
        """Should generate an action plan for a detected issue."""
        issues = [
            DetectedIssue(
                issue_id="ISS-001",
                category=IssueCategory.SAAS_UNDERUTILIZATION,
                severity=IssueSeverity.MEDIUM,
                title="Test underutilized SaaS",
                description="Test tool at 15% utilization",
                affected_entity_id="SUB-001",
                affected_entity_type="saas",
                potential_savings_inr=120000,
                evidence={"utilization_ratio": 0.15},
            ),
        ]
        actions = self.agent.run(issues)
        self.assertEqual(len(actions), 1)
        self.assertGreater(actions[0].estimated_savings_inr, 0)
        self.assertGreater(actions[0].confidence_score, 0)
        self.assertLess(actions[0].risk_score, 1.0)

    def test_deterministic_output(self):
        """Same input should produce same output."""
        issues = [
            DetectedIssue(
                issue_id="ISS-003",
                category=IssueCategory.DUPLICATE_VENDOR,
                severity=IssueSeverity.HIGH,
                title="Duplicate vendor",
                description="Two vendors for same category",
                affected_entity_id="PO-001",
                affected_entity_type="procurement",
                potential_savings_inr=500000,
                evidence={},
            ),
        ]
        result1 = self.agent.run(issues)
        result2 = self.agent.run(issues)
        self.assertEqual(len(result1), len(result2))
        self.assertEqual(result1[0].title, result2[0].title)
        self.assertEqual(result1[0].estimated_savings_inr, result2[0].estimated_savings_inr)


class TestImpactAgent(unittest.TestCase):
    """Unit tests for ImpactAgent."""

    def setUp(self):
        self.agent = ImpactAgent()

    def test_calculates_realized_savings(self):
        """Realized savings from verified actions."""
        actions = [
            ActionPlan(
                action_id="ACT-001", issue_id="ISS-001",
                action_type=ActionType.DOWNGRADE_PLAN,
                title="Downgrade plan",
                description="Test",
                target_entity_id="SUB-001",
                estimated_savings_inr=120000,
                roi_estimate=4.0,
                risk_score=0.2,
                confidence_score=0.9,
                justification="Test",
            ),
        ]
        executions = [
            ExecutionLog(
                execution_id="EX-001",
                action_id="ACT-001",
                action_type=ActionType.DOWNGRADE_PLAN,
                status=ActionStatus.EXECUTED,
                target_entity_id="SUB-001",
                attempts=1,
                verified=True,
                response_payload={"status": "success"},
            ),
        ]
        issues = [
            DetectedIssue(
                issue_id="ISS-001",
                category=IssueCategory.SAAS_UNDERUTILIZATION,
                severity=IssueSeverity.MEDIUM,
                title="Test",
                description="Test",
                affected_entity_id="SUB-001",
                affected_entity_type="saas",
                potential_savings_inr=120000,
            ),
        ]
        report = self.agent.run(1, actions, executions, issues)
        self.assertGreater(report.realized_savings_inr, 0)
        self.assertGreater(report.total_impact_inr, 0)
        self.assertTrue(len(report.summary) > 0)


class TestFullPipeline(unittest.TestCase):
    """Integration test: full pipeline end-to-end."""

    def test_full_pipeline_deterministic(self):
        """Complete pipeline should run and produce deterministic outputs."""
        ingestion = IngestionAgent()
        detection = DetectionAgent()
        decision = DecisionAgent()
        execution = ExecutionAgent()
        verification = VerificationAgent()
        impact = ImpactAgent()

        # Stage 1: Ingest
        data = ingestion.run()
        self.assertIn("procurement", data)
        self.assertIn("saas", data)
        self.assertIn("cloud", data)
        self.assertIn("sla", data)
        total = sum(len(v) for v in data.values())
        self.assertGreater(total, 0, "Should ingest some records")

        # Stage 2: Detect
        issues = detection.run(data)
        self.assertGreater(len(issues), 0, "Should detect issues")

        # Stage 3: Decide
        actions = decision.run(issues)
        self.assertGreater(len(actions), 0, "Should generate actions")

        # Stage 4: Execute
        exec_logs = execution.run(actions)
        self.assertEqual(len(exec_logs), len(actions))
        executed = sum(1 for l in exec_logs if l.status.value in ("executed", "verified"))
        self.assertGreater(executed, 0, "Some actions should execute")

        # Stage 5: Verify
        verified = verification.run(actions, exec_logs)
        verified_count = sum(1 for l in verified if l.verified)
        self.assertGreater(verified_count, 0, "Some executions should verify")

        # Stage 6: Impact
        report = impact.run(1, actions, verified, issues)
        self.assertGreater(report.total_impact_inr, 0, "Should compute positive impact")

        # Determinism: run again, same results
        data2 = ingestion.run()
        issues2 = detection.run(data2)
        self.assertEqual(len(issues), len(issues2), "Detection should be deterministic")

        print(f"\n{'=' * 60}")
        print(f"  INTEGRATION TEST PASSED")
        print(f"  Records: {total} | Issues: {len(issues)} | Actions: {len(actions)}")
        print(f"  Executed: {executed} | Verified: {verified_count}")
        print(f"  Total Impact: INR {report.total_impact_inr:,.0f}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
