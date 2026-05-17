"""Map a customer phone to a tenant on a shared trial WhatsApp line (wa_trial_map).

Usage:

    python backend/tools/map_trial_customer.py --wa-number-id <uuid> --customer-phone +9198... --client-id <uuid>
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wa-number-id", required=True, help="wa_numbers.id for the shared trial line")
    p.add_argument("--customer-phone", required=True, help="Customer E.164 e.g. +919876543210")
    p.add_argument("--client-id", required=True)
    args = p.parse_args()

    phone = args.customer_phone.strip()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO wa_trial_map (wa_number_id, customer_phone_e164, client_id)
                VALUES (
                  CAST(:wid AS uuid),
                  :phone,
                  CAST(:cid AS uuid)
                )
                ON CONFLICT (wa_number_id, customer_phone_e164) DO UPDATE
                SET client_id = EXCLUDED.client_id
                """
            ),
            {
                "wid": args.wa_number_id.strip(),
                "phone": phone,
                "cid": args.client_id.strip(),
            },
        )
    print(f"OK: trial map {phone} -> client {args.client_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
