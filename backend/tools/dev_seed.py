from __future__ import annotations

import os
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    """
    Seeds minimal rows needed for local testing:
    - api_clients
    - wa_numbers with meta_phone_number_id mapping to that client

    Usage:
      python backend/tools/dev_seed.py --meta-phone-number-id <PHONE_NUMBER_ID>
    """

    args = sys.argv[1:]
    if "--meta-phone-number-id" not in args:
        print("Missing required arg: --meta-phone-number-id <PHONE_NUMBER_ID>")
        return 2
    i = args.index("--meta-phone-number-id")
    try:
        meta_phone_number_id = args[i + 1].strip()
    except Exception:
        print("Missing value after --meta-phone-number-id")
        return 2

    if not meta_phone_number_id:
        print("meta phone_number_id cannot be empty")
        return 2

    if meta_phone_number_id.upper() in ("YOUR_META_PHONE_NUMBER_ID", "REPLACE_ME"):
        print("Replace the placeholder with your real Meta Cloud API phone_number_id (from Meta Developer / WhatsApp setup).")
        return 2

    business_name = os.environ.get("DEV_BUSINESS_NAME", "Test Client")
    category = os.environ.get("DEV_CATEGORY", "restaurant")
    phone_e164 = os.environ.get("DEV_WA_PHONE_E164", "+911111111111")

    with engine.begin() as conn:
        client_id = conn.execute(
            text(
                """
                INSERT INTO api_clients (business_name, category, entitlement_plan)
                VALUES (:bn, :cat, 'trial')
                RETURNING id
                """
            ),
            {"bn": business_name, "cat": category},
        ).scalar_one()

        wa_id = conn.execute(
            text(
                """
                INSERT INTO wa_numbers (phone_e164, type, ownership, client_id, meta_phone_number_id, status)
                VALUES (:pe, 'PROD', 'ZY_OWNED', CAST(:cid AS uuid), :pid, 'active')
                RETURNING id
                """
            ),
            {"pe": phone_e164, "cid": str(client_id), "pid": meta_phone_number_id},
        ).scalar_one()

    print("Seeded OK")
    print(f"CLIENT_ID={client_id}")
    print(f"WA_NUMBER_ID={wa_id}")
    print(f"META_PHONE_NUMBER_ID={meta_phone_number_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

