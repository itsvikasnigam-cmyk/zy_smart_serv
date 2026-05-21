"""Set Chat S cost model assumptions in ops_runtime_config.

Examples:
  python backend/tools/set_cost_model.py --mode local --threshold 100
  python backend/tools/set_cost_model.py --mode cloud --cloud-per-1k 0.15 --starter-monthly 999
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.cost_model import COST_MODEL_KEY, merge_cost_model
from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["local", "cloud"])
    p.add_argument("--avg-tokens", type=float)
    p.add_argument("--local-per-1k", type=float)
    p.add_argument("--cloud-per-1k", type=float)
    p.add_argument("--threshold", type=float, help="Daily cost alert threshold INR")
    p.add_argument("--starter-monthly", type=float)
    p.add_argument("--growth-monthly", type=float)
    p.add_argument("--pro-monthly", type=float)
    args = p.parse_args()

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :key"),
            {"key": COST_MODEL_KEY},
        ).fetchone()
        model = merge_cost_model(row[0] if row else None)
        if args.mode:
            model["mode"] = args.mode
        if args.avg_tokens is not None:
            model["avg_tokens_per_ai_reply"] = args.avg_tokens
        if args.local_per_1k is not None:
            model["local_ai_cost_per_1k_tokens_inr"] = args.local_per_1k
        if args.cloud_per_1k is not None:
            model["cloud_ai_cost_per_1k_tokens_inr"] = args.cloud_per_1k
        if args.threshold is not None:
            model["daily_cost_alert_threshold_inr"] = args.threshold
        prices = dict(model.get("monthly_revenue_inr_by_plan") or {})
        if args.starter_monthly is not None:
            prices["starter"] = args.starter_monthly
        if args.growth_monthly is not None:
            prices["growth"] = args.growth_monthly
        if args.pro_monthly is not None:
            prices["pro"] = args.pro_monthly
        model["monthly_revenue_inr_by_plan"] = prices
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:key, CAST(:value AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"key": COST_MODEL_KEY, "value": json.dumps(model)},
        )

    print(f"OK: {COST_MODEL_KEY} updated")
    print(json.dumps(model, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
