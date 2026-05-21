"""Chat S: lightweight local/cloud AI cost and margin assumptions."""

from __future__ import annotations

from typing import Any

COST_MODEL_KEY = "metrics.cost_model"

DEFAULT_COST_MODEL: dict[str, Any] = {
    "currency": "INR",
    "mode": "local",
    "avg_tokens_per_ai_reply": 350,
    "local_ai_cost_per_1k_tokens_inr": 0.02,
    "cloud_ai_cost_per_1k_tokens_inr": 0.15,
    "monthly_revenue_inr_by_plan": {
        "trial": 0,
        "starter": 999,
        "growth": 2999,
        "pro": 9999,
        "churned": 0,
    },
    "daily_cost_alert_threshold_inr": 100,
}


def merge_cost_model(value_json: Any | None) -> dict[str, Any]:
    """Merge DB JSON with conservative defaults; invalid values fall back."""
    merged = dict(DEFAULT_COST_MODEL)
    merged["monthly_revenue_inr_by_plan"] = dict(DEFAULT_COST_MODEL["monthly_revenue_inr_by_plan"])
    if isinstance(value_json, dict):
        for key, value in value_json.items():
            if key == "monthly_revenue_inr_by_plan" and isinstance(value, dict):
                merged["monthly_revenue_inr_by_plan"].update(value)
            else:
                merged[key] = value
    return merged


def ai_cost_per_invocation_inr(model: dict[str, Any]) -> float:
    mode = str(model.get("mode") or "local").strip().lower()
    rate_key = "cloud_ai_cost_per_1k_tokens_inr" if mode == "cloud" else "local_ai_cost_per_1k_tokens_inr"
    try:
        avg_tokens = float(model.get("avg_tokens_per_ai_reply") or DEFAULT_COST_MODEL["avg_tokens_per_ai_reply"])
        rate = float(model.get(rate_key) or 0)
    except (TypeError, ValueError):
        avg_tokens = float(DEFAULT_COST_MODEL["avg_tokens_per_ai_reply"])
        rate = 0.0
    return max(0.0, avg_tokens) * max(0.0, rate) / 1000.0


def monthly_revenue_for_plan_inr(model: dict[str, Any], plan: str | None) -> float:
    plan_key = (plan or "trial").strip().lower()
    prices = model.get("monthly_revenue_inr_by_plan") or {}
    try:
        return float(prices.get(plan_key, 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def alert_threshold_inr(model: dict[str, Any]) -> float:
    try:
        return float(model.get("daily_cost_alert_threshold_inr") or 0)
    except (TypeError, ValueError):
        return 0.0
