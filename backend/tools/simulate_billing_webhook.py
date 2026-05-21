"""POST a signed billing webhook to local billing_api (Chat R dev tool).

Usage:
  . .\\dev-env.ps1
  python backend/tools/dev_seed.py   # note CLIENT_ID=...
  python backend/tools/seed_bill_plans.py --provider razorpay --external-plan-id plan_dev_starter --plan-code starter
  python backend/tools/simulate_billing_webhook.py --provider razorpay --event activated --client-id <UUID>
  python backend/tools/simulate_billing_webhook.py --provider razorpay --event churned --client-id <UUID> --subscription-id sub_dev_xxx
  python backend/tools/show_client_billing.py --client-id <UUID>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.apps.billing_api.verify_signatures import build_paddle_signature, build_razorpay_signature
from backend.apps.billing_api.webhook_fixtures import (
    paddle_subscription_activated,
    paddle_subscription_canceled,
    razorpay_subscription_activated,
    razorpay_subscription_cancelled,
)
from backend.shared.config import settings

BASE = "http://127.0.0.1:8086"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["razorpay", "paddle"], required=True)
    ap.add_argument("--event", choices=["activated", "churned"], required=True)
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--plan", default="starter", choices=["starter", "growth", "pro"])
    ap.add_argument("--external-plan-id", default=None, help="Razorpay plan_id / Paddle price_id")
    ap.add_argument("--subscription-id", default=None, help="Required for churned if reusing sub id")
    ap.add_argument("--base-url", default=BASE)
    args = ap.parse_args()

    ext_plan = args.external_plan_id or f"plan_dev_{args.plan}"
    cid = args.client_id.strip()

    if args.provider == "razorpay":
        secret = (settings.billing_razorpay_webhook_secret or "").strip()
        if not secret:
            print("FAIL: BILLING_RAZORPAY_WEBHOOK_SECRET not set in backend/.env")
            return 1
        if args.event == "activated":
            payload = razorpay_subscription_activated(
                client_id=cid,
                plan_id=ext_plan,
                entitlement_plan=args.plan,
                subscription_id=args.subscription_id,
            )
        else:
            sub = args.subscription_id
            if not sub:
                print("FAIL: --subscription-id required for razorpay churned (or run activated first)")
                return 1
            payload = razorpay_subscription_cancelled(client_id=cid, subscription_id=sub)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = build_razorpay_signature(body, secret)
        url = f"{args.base_url.rstrip('/')}/webhooks/razorpay"
        headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    else:
        secret = (settings.billing_paddle_webhook_secret or "").strip()
        if not secret:
            print("FAIL: BILLING_PADDLE_WEBHOOK_SECRET not set in backend/.env")
            return 1
        if args.event == "activated":
            payload = paddle_subscription_activated(
                client_id=cid,
                price_id=ext_plan,
                entitlement_plan=args.plan,
                subscription_id=args.subscription_id,
            )
        else:
            sub = args.subscription_id
            if not sub:
                print("FAIL: --subscription-id required for paddle churned")
                return 1
            payload = paddle_subscription_canceled(client_id=cid, subscription_id=sub)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = build_paddle_signature(body, secret)
        url = f"{args.base_url.rstrip('/')}/webhooks/paddle"
        headers = {"Paddle-Signature": sig, "Content-Type": "application/json"}

    print(f"POST {url}")
    print(f"event={args.event} provider={args.provider} client_id={cid}")
    try:
        r = httpx.post(url, content=body, headers=headers, timeout=30.0)
    except Exception as e:
        print(f"FAIL request: {type(e).__name__}: {e}")
        return 1
    print(f"HTTP {r.status_code}")
    print(r.text[:2000])
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
