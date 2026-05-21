"""Point wa_numbers.meta_phone_number_id at your Meta Cloud API id (fixes unable_to_route_no_mapping).

Usage:

    cd ...\\empty-window; . .\\dev-env.ps1
    python backend/tools/link_meta_phone.py --meta-phone-number-id 1098044196727032
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser(description="Link Meta phone_number_id to first tenant (or --client-id).")
    p.add_argument("--meta-phone-number-id", required=True)
    p.add_argument("--client-id", default="", help="Optional; default = oldest api_clients row")
    p.add_argument("--phone-e164", default="+911111111111", help="wa_numbers.phone_e164 if inserting new row")
    args = p.parse_args()
    meta_id = args.meta_phone_number_id.strip()
    if not meta_id.isdigit():
        print("ERROR: meta_phone_number_id should be digits only (from Meta dashboard).")
        return 1

    with engine.begin() as conn:
        cid = (args.client_id or "").strip()
        if not cid:
            row = conn.execute(
                text("SELECT id::text FROM api_clients ORDER BY created_at ASC LIMIT 1")
            ).fetchone()
            if not row:
                print("ERROR: no api_clients. Run dev_seed.py first.")
                return 1
            cid = row[0]

        other = conn.execute(
            text(
                """
                SELECT client_id::text FROM wa_numbers
                WHERE meta_phone_number_id = :pid AND client_id IS DISTINCT FROM CAST(:cid AS uuid)
                LIMIT 1
                """
            ),
            {"pid": meta_id, "cid": cid},
        ).fetchone()
        if other:
            print(f"ERROR: meta_phone_number_id already used by another client_id={other[0]}")
            return 1

        existing = conn.execute(
            text(
                """
                SELECT id::text, meta_phone_number_id
                FROM wa_numbers
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"cid": cid},
        ).fetchone()

        if existing:
            wid, old_pid = existing[0], existing[1]
            conn.execute(
                text(
                    """
                    UPDATE wa_numbers
                    SET meta_phone_number_id = :pid, status = 'active'
                    WHERE id = CAST(:wid AS uuid)
                    """
                ),
                {"pid": meta_id, "wid": wid},
            )
            print(f"OK: updated wa_numbers {wid}")
            print(f"  client_id={cid}")
            print(f"  meta_phone_number_id: {old_pid!r} -> {meta_id}")
        else:
            wid = conn.execute(
                text(
                    """
                    INSERT INTO wa_numbers (
                      phone_e164, type, ownership, client_id, meta_phone_number_id, status
                    )
                    VALUES (:pe, 'PROD', 'ZY_OWNED', CAST(:cid AS uuid), :pid, 'active')
                    RETURNING id::text
                    """
                ),
                {"pe": args.phone_e164.strip(), "cid": cid, "pid": meta_id},
            ).scalar_one()
            print(f"OK: inserted wa_numbers {wid}")
            print(f"  client_id={cid}")
            print(f"  meta_phone_number_id={meta_id}")

    print("\nNext:")
    print(f'  python backend\\tools\\dev_send_inbound.py --meta-phone-number-id {meta_id} --from +919876543210 --text "hello gate 1 test"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
