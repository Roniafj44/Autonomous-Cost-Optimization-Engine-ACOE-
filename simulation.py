"""
ACOE -- What-If Simulation Engine
Simulate action outcomes before execution to compare strategies.
"""

from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime

logger = logging.getLogger("acoe.simulation")


class SimulationEngine:
    """
    Run what-if scenarios:
    'If action X is applied, what savings result?'
    Compare multiple strategies side by side.
    """

    def simulate_action(self, action, issues: list) -> dict:
        """Simulate a single action's outcome."""
        issue = next((i for i in issues if i.issue_id == action.issue_id), None)

        # Base savings
        base_savings = action.estimated_savings_inr
        risk_adjusted = base_savings * (1 - action.risk_score)
        confidence_adjusted = risk_adjusted * action.confidence_score

        # Time horizons
        monthly = base_savings / 12
        quarterly = base_savings / 4
        annual = base_savings

        return {
            "simulation_id": f"SIM-{uuid.uuid4().hex[:8].upper()}",
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "title": action.title,
            "base_savings_inr": round(base_savings, 2),
            "risk_adjusted_savings_inr": round(risk_adjusted, 2),
            "confidence_adjusted_savings_inr": round(confidence_adjusted, 2),
            "monthly_impact_inr": round(monthly, 2),
            "quarterly_impact_inr": round(quarterly, 2),
            "annual_impact_inr": round(annual, 2),
            "risk_score": action.risk_score,
            "confidence_score": action.confidence_score,
            "roi_estimate": action.roi_estimate,
        }

    def compare_strategies(self, actions: list, issues: list) -> dict:
        """
        Compare all actions as alternative strategies.
        Returns ranked comparison with aggregate impact.
        """
        simulations = []
        for action in actions:
            sim = self.simulate_action(action, issues)
            simulations.append(sim)

        # Sort by confidence-adjusted savings
        simulations.sort(
            key=lambda s: s["confidence_adjusted_savings_inr"], reverse=True
        )

        # Aggregate
        total_base = sum(s["base_savings_inr"] for s in simulations)
        total_adjusted = sum(s["confidence_adjusted_savings_inr"] for s in simulations)
        avg_risk = (
            sum(s["risk_score"] for s in simulations) / max(len(simulations), 1)
        )
        avg_confidence = (
            sum(s["confidence_score"] for s in simulations) / max(len(simulations), 1)
        )

        return {
            "comparison_id": f"CMP-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.utcnow().isoformat(),
            "total_actions": len(simulations),
            "aggregate": {
                "total_base_savings_inr": round(total_base, 2),
                "total_adjusted_savings_inr": round(total_adjusted, 2),
                "average_risk": round(avg_risk, 4),
                "average_confidence": round(avg_confidence, 4),
            },
            "strategies": simulations,
            "recommendation": simulations[0]["title"] if simulations else "No actions available",
        }

    def what_if(self, scenario: str, actions: list, issues: list) -> dict:
        """
        Run a named what-if scenario.
        Scenarios: 'aggressive', 'conservative', 'balanced'
        """
        if scenario == "aggressive":
            # Take all actions regardless of risk
            filtered = actions
        elif scenario == "conservative":
            # Only low-risk, high-confidence
            filtered = [a for a in actions if a.risk_score < 0.30 and a.confidence_score > 0.80]
        elif scenario == "balanced":
            # Default thresholds
            filtered = [a for a in actions if a.risk_score < 0.50 and a.confidence_score > 0.60]
        else:
            filtered = actions

        comparison = self.compare_strategies(filtered, issues)
        comparison["scenario"] = scenario
        comparison["filtered_count"] = len(filtered)
        comparison["original_count"] = len(actions)
        return comparison
