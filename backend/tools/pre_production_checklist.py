"""Print pre-production readiness (env + DB) before real WhatsApp + billing test.

Usage:

    cd ...\\empty-window; . .\\dev-env.ps1
    python backend/tools/pre_production_checklist.py
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import text

from backend.shared.config import settings
from backend.shared.db import engine


def _ok(label: str, yes: bool, detail: str = "") -> None:
    mark = "OK" if yes else "MISSING"
    extra = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{extra}")


def main() -> int:
    print("=== Pre-production gate (local checklist) ===\n")

    print("Environment (set in .env or shell):")
    _ok("DATABASE_URL", bool(os.environ.get("DATABASE_URL")), os.environ.get("DATABASE_URL", "")[:60])
    _ok("CLIENT_API_JWT_SECRET", bool(settings.client_api_jwt_secret))
    _ok("META_VERIFY_TOKEN", bool(settings.meta_verify_token))
    _ok("META_APP_SECRET", bool(settings.meta_app_secret), "required for signed Meta webhooks in prod")
    _ok("META_ACCESS_TOKEN", bool(settings.meta_access_token), "required for real outbound WhatsApp")
    _ok("BILLING_RAZORPAY_KEY_ID", bool(settings.billing_razorpay_key_id))
    _ok("BILLING_RAZORPAY_KEY_SECRET", bool(settings.billing_razorpay_key_secret))
    _ok("BILLING_RAZORPAY_WEBHOOK_SECRET", bool(settings.billing_razorpay_webhook_secret))
    _ok("BILLING_PADDLE_API_KEY", bool(settings.billing_paddle_api_key), "optional if India-only")
    _ok("WA_GATEWAY_ALLOW_CLIENT_ID_HEADER", settings.wa_gateway_allow_client_id_header is False,
        "must stay false outside dev")

    print("\nDatabase:")
    try:
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            _ok("alembic_version", ver is not None, ver[0] if ver else "")
            clients = conn.execute(text("SELECT COUNT(*)::int FROM api_clients")).scalar_one()
            wa = conn.execute(
                text(
                    "SELECT COUNT(*)::int FROM wa_numbers WHERE meta_phone_number_id IS NOT NULL"
                )
            ).scalar_one()
            plans = conn.execute(text("SELECT COUNT(*)::int FROM bill_plans WHERE active")).scalar_one()
            _ok("api_clients", clients > 0, f"count={clients}")
            _ok("wa_numbers with meta_phone_number_id", wa > 0, f"count={wa}")
            _ok("bill_plans (active)", plans > 0, f"count={plans}")
    except Exception as e:
        print(f"  [ERROR] DB: {e}")
        return 1

    print("\nServices to run (separate terminals):")
    print("  8081  wa_gateway        — Meta webhooks (public HTTPS URL in Meta console)")
    print("  8083  ai_engine         — POST /ai/respond")
    print("  8085  client_api        — login, inbox, signup")
    print("  8086  billing_api       — payments + provider webhooks")
    print("  8087  ops_api           — SOPs / runs")
    print("  workers: batch_processor, outbox_sender, metrics_rollup_worker (optional others)")

    print("\nTypical provision flow:")
    print("  1. python backend/tools/dev_seed.py --meta-phone-number-id <META_ID> --trial-days 14")
    print("  2. python backend/tools/seed_bill_plans.py --provider razorpay --external-plan-id <plan_id> --plan-code starter")
    print("  3. python backend/tools/setup_dev_logins.py   OR   POST /signup then login")
    print("  4. Point Meta + Razorpay webhooks at your public host")
    print("  5. flutter run (owner) + real message test")

    return 0


if __name__ == "__main__":
    sys.exit(main())
