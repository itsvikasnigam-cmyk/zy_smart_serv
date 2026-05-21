"""Add, remove, or list customer blocklist / DND rows (Chat V).

Usage:
  python backend/tools/manage_customer_block.py --client-id <uuid> --phone 919769825350 --add --type blocklist --reason "spam"
  python backend/tools/manage_customer_block.py --client-id <uuid> --phone 919769825350 --remove
  python backend/tools/manage_customer_block.py --client-id <uuid> --list
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.apps.wa_gateway.meta_payload import normalize_customer_phone_for_route
from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser(description="Manage customer_blocks for Chat V.")
    p.add_argument("--client-id", required=True)
    p.add_argument("--phone", default=None, help="E.164 digits only or with +")
    p.add_argument("--add", action="store_true")
    p.add_argument("--remove", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--type", choices=["blocklist", "dnd"], default="blocklist")
    p.add_argument("--reason", default=None)
    p.add_argument("--source", default="manual")
    args = p.parse_args()
    cid = args.client_id.strip()

    if args.list:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT customer_phone_e164, block_type, reason, active, created_at
                    FROM customer_blocks
                    WHERE client_id = CAST(:cid AS uuid)
                    ORDER BY created_at DESC
                    """
                ),
                {"cid": cid},
            ).all()
        if not rows:
            print("(no blocks)")
            return 0
        for r in rows:
            print(f"{r[0]}\t{r[1]}\tactive={r[3]}\t{r[2] or ''}\t{r[4]}")
        return 0

    if not args.phone:
        print("ERROR: --phone required for --add / --remove", file=sys.stderr)
        return 2

    phone = normalize_customer_phone_for_route(args.phone)

    if args.remove:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE customer_blocks
                    SET active = false, updated_at = now()
                    WHERE client_id = CAST(:cid AS uuid) AND customer_phone_e164 = :phone
                    """
                ),
                {"cid": cid, "phone": phone},
            )
        print(f"OK: deactivated block for {phone}")
        return 0

    if not args.add:
        print("ERROR: specify --add, --remove, or --list", file=sys.stderr)
        return 2

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO customer_blocks (
                  client_id, customer_phone_e164, block_type, reason, source, active
                )
                VALUES (
                  CAST(:cid AS uuid), :phone, :bt, :reason, :source, true
                )
                ON CONFLICT (client_id, customer_phone_e164) DO UPDATE SET
                  block_type = EXCLUDED.block_type,
                  reason = EXCLUDED.reason,
                  source = EXCLUDED.source,
                  active = true,
                  updated_at = now()
                """
            ),
            {
                "cid": cid,
                "phone": phone,
                "bt": args.type,
                "reason": args.reason,
                "source": args.source,
            },
        )
    print(f"OK: block active for {phone} ({args.type})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
