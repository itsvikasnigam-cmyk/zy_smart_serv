"""Show api_clients entitlement + bill_subscriptions for a client (Chat R).

Usage:
  python backend/tools/show_client_billing.py --client-id <UUID>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.db import engine


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    args = ap.parse_args()

    with engine.connect() as conn:
        c = conn.execute(
            text(
                """
                SELECT entitlement_plan::text, billing_provider, billing_plan_code, trial_end
                FROM api_clients
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": args.client_id},
        ).fetchone()
        subs = conn.execute(
            text(
                """
                SELECT provider, external_subscription_id, status, plan_code, updated_at
                FROM bill_subscriptions
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY updated_at DESC
                LIMIT 5
                """
            ),
            {"cid": args.client_id},
        ).all()
        events = conn.execute(
            text(
                """
                SELECT provider, event_type, applied, received_at
                FROM bill_events
                WHERE payload::text LIKE :needle
                ORDER BY received_at DESC
                LIMIT 5
                """
            ),
            {"needle": f"%{args.client_id}%"},
        ).all()

    if not c:
        print("client not found")
        return 1
    print(f"entitlement_plan={c[0]} billing_provider={c[1]} billing_plan_code={c[2]} trial_end={c[3]}")
    print("bill_subscriptions:")
    for s in subs:
        print(f"  {s}")
    print("recent bill_events (payload contains client_id):")
    for e in events:
        print(f"  {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
