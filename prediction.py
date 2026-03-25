"""
ACOE -- Time-Series Cost Leak Prediction
Lightweight forecasting using moving averages and simple regression.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

import numpy as np

from config import get_config

logger = logging.getLogger("acoe.prediction")


class CostPredictor:
    """
    Predict future inefficiencies and upcoming SLA risks using
    moving averages and simple linear regression.
    """

    def __init__(self):
        self._cfg = get_config()

    def predict_savings_trend(self, history: list[dict]) -> dict:
        """
        Predict future savings based on cycle history.
        history: list of dicts with 'cycle_id' and 'total_savings' keys.
        """
        if len(history) < 2:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 cycles for prediction",
                "predictions": [],
            }

        # Extract values (most recent first, so reverse)
        values = [h.get("total_savings", 0) for h in reversed(history)]
        cycles = list(range(1, len(values) + 1))

        method = self._cfg.get("prediction.method", "moving_average")
        horizon = self._cfg.get("prediction.forecast_horizon_months", 3)

        if method == "linear_regression":
            predictions = self._linear_regression_forecast(cycles, values, horizon)
        else:
            predictions = self._moving_average_forecast(values, horizon)

        trend = "increasing" if len(values) > 1 and values[-1] > values[0] else "decreasing"

        return {
            "status": "ok",
            "method": method,
            "data_points": len(values),
            "trend": trend,
            "current_avg": round(np.mean(values), 2),
            "predictions": predictions,
        }

    def predict_sla_risks(self, sla_metrics: list) -> list[dict]:
        """
        Predict which SLAs are likely to breach based on current trajectory.
        Uses linear extrapolation of compliance ratio.
        """
        predictions = []
        for sla in sla_metrics:
            compliance = sla.compliance_ratio
            hours_left = sla.hours_to_breach

            # Simple risk score: lower compliance + fewer hours = higher risk
            if hours_left <= 0:
                risk_level = "BREACHED"
                risk_score = 1.0
            elif hours_left < 24:
                risk_level = "CRITICAL"
                risk_score = 0.9
            elif hours_left < 48:
                risk_level = "HIGH"
                risk_score = 0.7
            elif compliance < 0.95:
                risk_level = "MODERATE"
                risk_score = 0.5
            else:
                risk_level = "LOW"
                risk_score = 0.2

            # Estimate time to breach if underperforming
            if compliance < 1.0 and hours_left > 0:
                # Rate of degradation (simplified)
                degradation_rate = (1.0 - compliance) / max(hours_left, 1)
                estimated_breach_hours = hours_left * compliance
            else:
                degradation_rate = 0
                estimated_breach_hours = float("inf")

            predictions.append({
                "sla_id": sla.sla_id,
                "service": sla.service_name,
                "vendor": sla.vendor_name,
                "metric": sla.metric_name,
                "current_compliance": round(compliance, 4),
                "hours_to_breach": round(hours_left, 1),
                "risk_level": risk_level,
                "risk_score": round(risk_score, 3),
                "estimated_breach_hours": round(estimated_breach_hours, 1) if estimated_breach_hours != float("inf") else None,
                "penalty_at_risk_inr": sla.breach_penalty_inr,
            })

        # Sort by risk score descending
        predictions.sort(key=lambda p: p["risk_score"], reverse=True)
        return predictions

    def predict_cost_leaks(self, saas_data: list, cloud_data: list) -> list[dict]:
        """
        Predict future cost leaks by identifying assets with declining utilization.
        """
        leaks = []

        for sub in saas_data:
            ratio = sub.utilization_ratio
            if ratio < 0.50:
                monthly_waste = sub.monthly_cost_inr * (1 - ratio)
                projected_waste_3mo = monthly_waste * 3

                leaks.append({
                    "entity_id": sub.subscription_id,
                    "entity_type": "saas",
                    "name": sub.product_name,
                    "current_utilization": round(ratio, 3),
                    "monthly_waste_inr": round(monthly_waste, 2),
                    "projected_3mo_waste_inr": round(projected_waste_3mo, 2),
                    "severity": "high" if ratio < 0.25 else "medium",
                    "recommendation": "Cancel" if ratio < 0.15 else "Downgrade",
                })

        for res in cloud_data:
            ratio = res.utilization_ratio
            if ratio < 0.40:
                monthly_waste = res.monthly_cost_inr * (1 - ratio)
                projected_waste_3mo = monthly_waste * 3

                leaks.append({
                    "entity_id": res.resource_id,
                    "entity_type": "cloud",
                    "name": f"{res.resource_type} ({res.provider})",
                    "current_utilization": round(ratio, 3),
                    "monthly_waste_inr": round(monthly_waste, 2),
                    "projected_3mo_waste_inr": round(projected_waste_3mo, 2),
                    "severity": "high" if ratio < 0.20 else "medium",
                    "recommendation": "Right-size" if ratio > 0.10 else "Decommission",
                })

        leaks.sort(key=lambda l: l["projected_3mo_waste_inr"], reverse=True)
        return leaks

    # ── Forecasting Methods ──────────────────────────────────────────────

    def _moving_average_forecast(self, values: list, horizon: int) -> list[dict]:
        """Simple moving average forecast."""
        window = min(len(values), 5)
        ma = np.mean(values[-window:])
        predictions = []
        for i in range(1, horizon + 1):
            predictions.append({
                "period": f"month_{i}",
                "predicted_savings_inr": round(float(ma), 2),
                "method": "moving_average",
                "window": window,
            })
        return predictions

    def _linear_regression_forecast(self, x: list, y: list, horizon: int) -> list[dict]:
        """Simple linear regression forecast."""
        n = len(x)
        x_arr = np.array(x, dtype=float)
        y_arr = np.array(y, dtype=float)

        x_mean = np.mean(x_arr)
        y_mean = np.mean(y_arr)

        numerator = np.sum((x_arr - x_mean) * (y_arr - y_mean))
        denominator = np.sum((x_arr - x_mean) ** 2)

        if denominator == 0:
            return self._moving_average_forecast(y, horizon)

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        predictions = []
        for i in range(1, horizon + 1):
            future_x = n + i
            predicted = slope * future_x + intercept
            predictions.append({
                "period": f"month_{i}",
                "predicted_savings_inr": round(max(float(predicted), 0), 2),
                "method": "linear_regression",
                "slope": round(float(slope), 2),
                "intercept": round(float(intercept), 2),
            })
        return predictions
