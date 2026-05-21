from __future__ import annotations

from backend.shared.cost_model import (
    ai_cost_per_invocation_inr,
    alert_threshold_inr,
    merge_cost_model,
    monthly_revenue_for_plan_inr,
)


def test_cost_model_defaults_and_cost_per_invocation() -> None:
    model = merge_cost_model(None)
    assert model["mode"] == "local"
    assert ai_cost_per_invocation_inr(model) > 0


def test_cost_model_cloud_override() -> None:
    model = merge_cost_model(
        {
            "mode": "cloud",
            "avg_tokens_per_ai_reply": 1000,
            "cloud_ai_cost_per_1k_tokens_inr": 2.5,
            "monthly_revenue_inr_by_plan": {"starter": 1234},
            "daily_cost_alert_threshold_inr": 9,
        }
    )
    assert ai_cost_per_invocation_inr(model) == 2.5
    assert monthly_revenue_for_plan_inr(model, "starter") == 1234
    assert alert_threshold_inr(model) == 9
