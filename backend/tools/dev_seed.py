from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    """
    Seeds minimal rows needed for local testing:
    - api_clients
    - wa_numbers with meta_phone_number_id mapping to that client

    Safe to run multiple times: if this meta_phone_number_id or DEV_WA_PHONE_E164
    already exists, updates or no-ops instead of failing on unique constraints.

    Usage:
      python backend/tools/dev_seed.py --meta-phone-number-id <PHONE_NUMBER_ID>
    """

    parser = argparse.ArgumentParser(description="Seed api_clients + wa_numbers for Meta routing.")
    parser.add_argument("--meta-phone-number-id", required=True)
    parser.add_argument(
        "--trial-days",
        type=int,
        default=3,
        help="Set api_clients.trial_end to now+N days (default 3, v5.3 / phase 2)",
    )
    parser.add_argument(
        "--force-meta-phone-number-id",
        action="store_true",
        help="Overwrite an existing wa_numbers.meta_phone_number_id (default: keep current id)",
    )
    ns = parser.parse_args()
    meta_phone_number_id = ns.meta_phone_number_id.strip()
    trial_days = max(1, int(ns.trial_days))

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
        row = conn.execute(
            text(
                """
                SELECT id, client_id
                FROM wa_numbers
                WHERE meta_phone_number_id = :pid
                LIMIT 1
                """
            ),
            {"pid": meta_phone_number_id},
        ).fetchone()
        if row:
            wa_id, client_id = row[0], row[1]
            print("Already seeded (meta_phone_number_id already mapped).")
            print(f"CLIENT_ID={client_id}")
            print(f"WA_NUMBER_ID={wa_id}")
            print(f"META_PHONE_NUMBER_ID={meta_phone_number_id}")
            return 0

        row = conn.execute(
            text(
                """
                SELECT id, client_id
                FROM wa_numbers
                WHERE phone_e164 = :pe
                LIMIT 1
                """
            ),
            {"pe": phone_e164},
        ).fetchone()
        if row:
            wa_id, cid = row[0], row[1]
            current_meta = conn.execute(
                text(
                    """
                    SELECT meta_phone_number_id
                    FROM wa_numbers
                    WHERE id = CAST(:wid AS uuid)
                    """
                ),
                {"wid": str(wa_id)},
            ).scalar_one()
            if (
                current_meta
                and current_meta != meta_phone_number_id
                and not ns.force_meta_phone_number_id
            ):
                print("SKIP: keeping existing meta_phone_number_id (will not overwrite).")
                print(f"  current: {current_meta}")
                print(f"  requested: {meta_phone_number_id}")
                print("Use link_meta_phone.py for your real Meta id, or pass --force-meta-phone-number-id.")
                print(f"CLIENT_ID={cid}")
                print(f"WA_NUMBER_ID={wa_id}")
                return 0
            if cid is None:
                client_id = conn.execute(
                    text(
                        """
                        INSERT INTO api_clients (business_name, category, entitlement_plan, trial_end)
                        VALUES (:bn, :cat, 'trial', timezone('utc', now()) + (:d || ' days')::interval)
                        RETURNING id
                        """
                    ),
                    {"bn": business_name, "cat": category, "d": trial_days},
                ).scalar_one()
                conn.execute(
                    text(
                        """
                        UPDATE wa_numbers
                        SET meta_phone_number_id = :pid,
                            client_id = CAST(:cid AS uuid),
                            type = 'PROD',
                            ownership = 'ZY_OWNED',
                            status = 'active'
                        WHERE id = CAST(:wid AS uuid)
                        """
                    ),
                    {"pid": meta_phone_number_id, "cid": str(client_id), "wid": str(wa_id)},
                )
            else:
                client_id = cid
                conn.execute(
                    text(
                        """
                        UPDATE wa_numbers
                        SET meta_phone_number_id = :pid,
                            status = 'active'
                        WHERE id = CAST(:wid AS uuid)
                        """
                    ),
                    {"pid": meta_phone_number_id, "wid": str(wa_id)},
                )
            print("Seeded OK (reused existing wa_numbers row for DEV_WA_PHONE_E164; set / refreshed meta_phone_number_id).")
            print(f"CLIENT_ID={client_id}")
            print(f"WA_NUMBER_ID={wa_id}")
            print(f"META_PHONE_NUMBER_ID={meta_phone_number_id}")
            return 0

        client_id = conn.execute(
            text(
                """
                INSERT INTO api_clients (business_name, category, entitlement_plan, trial_end)
                VALUES (:bn, :cat, 'trial', timezone('utc', now()) + (:d || ' days')::interval)
                RETURNING id
                """
            ),
            {"bn": business_name, "cat": category, "d": trial_days},
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
    print(f"TRIAL_DAYS={trial_days}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
