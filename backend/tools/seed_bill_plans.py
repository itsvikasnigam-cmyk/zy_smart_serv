"""Insert or update bill_plans rows for webhook → entitlement mapping.

Usage:

    python backend/tools/seed_bill_plans.py --provider razorpay --external-plan-id plan_xxx --plan-code starter --name "Starter"
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser(description="Seed bill_plans for billing webhooks.")
    p.add_argument("--provider", choices=["razorpay", "paddle"], required=True)
    p.add_argument("--external-plan-id", required=True, help="Razorpay plan_id or Paddle price_id")
    p.add_argument("--plan-code", choices=["starter", "growth", "pro"], required=True)
    p.add_argument("--name", default="", help="display_name")
    args = p.parse_args()

    display = args.name.strip() or args.plan_code.title()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO bill_plans (provider, external_plan_id, plan_code, display_name, active)
                VALUES (:p, :ext, :code, :dn, true)
                ON CONFLICT (provider, external_plan_id) DO UPDATE SET
                  plan_code = EXCLUDED.plan_code,
                  display_name = EXCLUDED.display_name,
                  active = true
                """
            ),
            {
                "p": args.provider,
                "ext": args.external_plan_id.strip(),
                "code": args.plan_code,
                "dn": display,
            },
        )
    print(f"OK: bill_plans {args.provider} / {args.external_plan_id} -> {args.plan_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
