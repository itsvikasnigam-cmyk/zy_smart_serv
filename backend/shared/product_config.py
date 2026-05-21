"""Product knobs from ops_runtime_config (Option C phase 2 — no redeploy for trial/limits)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

PRODUCT_TRIAL_DAYS_KEY = "product.trial_days_default"
USAGE_HARD_REPLY_KEY = "m2.usage_hard_customer_reply"
SERVICE_INACTIVE_REPLY_KEY = "m2.service_inactive_customer_reply"

# v5.3-WIN11 aligned defaults when DB key missing
DEFAULT_TRIAL_DAYS = 3
DEFAULT_USAGE_HARD_REPLY = (
    "You've reached today's message limit on your plan. "
    "Please upgrade or try again tomorrow — we're here to help when your plan allows more conversations."
)
DEFAULT_SERVICE_INACTIVE_REPLY = (
    "We're not able to continue this chat — your trial has ended or this workspace is inactive. "
    "Please complete billing or contact support to restore service."
)

# Blueprint v5.3: trial/starter hard cap 35 inbound customer messages per UTC day
PHASE2_USAGE_LIMITS: dict[str, Any] = {
    "trial": {"soft_warn": 30, "hard_block": 35},
    "starter": {"soft_warn": 30, "hard_block": 35},
    "growth": {"soft_warn": 50000, "hard_block": 60000},
    "pro": {"soft_warn": 200000, "hard_block": 250000},
    "churned": {"soft_warn": 0, "hard_block": 1},
    "_default": {"soft_warn": 30, "hard_block": 35},
}

PLAN_DISPLAY_ALIASES_KEY = "product.plan_display_aliases"


def _coerce_json_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _coerce_positive_int(raw: Any, default: int) -> int:
    if raw is None or isinstance(raw, bool):
        return default
    try:
        n = int(raw)
        return n if n >= 1 else default
    except (TypeError, ValueError):
        return default


def load_ops_json(conn: Connection, key: str) -> Any:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": key},
    ).fetchone()
    if not row:
        return None
    return row[0]


def load_trial_days_default(conn: Connection) -> int:
    raw = load_ops_json(conn, PRODUCT_TRIAL_DAYS_KEY)
    if isinstance(raw, int):
        return max(1, raw)
    if isinstance(raw, dict):
        return _coerce_positive_int(raw.get("days"), DEFAULT_TRIAL_DAYS)
    return _coerce_positive_int(raw, DEFAULT_TRIAL_DAYS)


def load_paywall_reply(conn: Connection, block_reason: str | None) -> str:
    key = USAGE_HARD_REPLY_KEY if block_reason == "usage_hard" else SERVICE_INACTIVE_REPLY_KEY
    default = DEFAULT_USAGE_HARD_REPLY if block_reason == "usage_hard" else DEFAULT_SERVICE_INACTIVE_REPLY
    raw = load_ops_json(conn, key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        t = raw.get("text") or raw.get("message")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return default


def plan_display_name(conn: Connection, entitlement_plan: str) -> str:
    """Map internal plan code to customer-facing label (e.g. growth → Enterprise)."""
    aliases = _coerce_json_dict(load_ops_json(conn, PLAN_DISPLAY_ALIASES_KEY))
    ent = entitlement_plan.strip().lower()
    label = aliases.get(ent)
    if isinstance(label, str) and label.strip():
        return label.strip()
  # v5.3 "Enterprise" maps to repo tier ``growth``
    if ent == "growth":
        return "Enterprise"
    return entitlement_plan.replace("_", " ").title()
