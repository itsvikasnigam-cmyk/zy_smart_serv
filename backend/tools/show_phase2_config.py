"""Print Option C phase 2 product config from ops_runtime_config.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/show_phase2_config.py
"""

from __future__ import annotations

import json

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.product_config import (
    PRODUCT_TRIAL_DAYS_KEY,
    load_trial_days_default,
    plan_display_name,
)
from backend.workers.usage_metrics_common import load_daily_inbound_limits_json


def main() -> int:
    with engine.connect() as conn:
        trial_days = load_trial_days_default(conn)
        limits = load_daily_inbound_limits_json(conn)
        print("=== Option C phase 2 ===")
        print(f"product.trial_days_default -> {trial_days} days")
        print("usage.daily_inbound_limits:")
        for plan in ("trial", "starter", "growth", "pro"):
            entry = limits.get(plan) or limits.get("_default") or {}
            print(f"  {plan}: soft_warn={entry.get('soft_warn')} hard_block={entry.get('hard_block')}")
        print(f"display growth tier as: {plan_display_name(conn, 'growth')}")
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = 'm2.usage_hard_customer_reply'")
        ).fetchone()
        if row and row[0]:
            print(f"usage_hard reply: {row[0]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
