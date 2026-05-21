"""Run one Razorpay webhook payload through process_razorpay_webhook (prints exception).

Usage:
  python backend/tools/diagnose_billing_webhook.py --client-id <UUID>
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.apps.billing_api.process_webhook import process_razorpay_webhook
from backend.apps.billing_api.webhook_fixtures import razorpay_subscription_activated
from backend.shared.db import engine


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    args = ap.parse_args()
    cid = args.client_id.strip()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id::text FROM api_clients WHERE id = CAST(:cid AS uuid)"),
            {"cid": cid},
        ).fetchone()
    if not row:
        print(f"FAIL: no api_clients row for id={cid}")
        return 1
    print(f"OK: client exists {row[0]}")

    payload = razorpay_subscription_activated(
        client_id=cid,
        plan_id="plan_dev_starter",
        entitlement_plan="starter",
    )
    try:
        with engine.begin() as conn:
            out = process_razorpay_webhook(conn, payload)
        print("OK:", out)
        return 0
    except Exception as e:
        print(f"ERR: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            with engine.connect() as conn:
                errs = conn.execute(
                    text(
                        """
                        SELECT provider, left(detail, 500), created_at
                        FROM bill_webhook_processing_errors
                        ORDER BY created_at DESC
                        LIMIT 3
                        """
                    )
                ).all()
                print("bill_webhook_processing_errors:", errs)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
