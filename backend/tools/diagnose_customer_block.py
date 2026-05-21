"""Verify customer_blocks row and gateway lookup for a phone (Chat V).

Usage:
  python backend/tools/diagnose_customer_block.py --client-id <uuid> --phone 919769825350
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.apps.wa_gateway.meta_payload import normalize_customer_phone_for_route
from backend.shared.customer_blocks import lookup_customer_block
from backend.shared.db import engine
from backend.shared.privacy_config import load_privacy_policy_engine


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", required=True)
    p.add_argument("--phone", required=True)
    args = p.parse_args()
    cid = args.client_id.strip()
    phone = normalize_customer_phone_for_route(args.phone)

    policy = load_privacy_policy_engine(engine)
    print("privacy.policy.blocklist_mode:", policy.blocklist_mode)

    with engine.connect() as conn:
        try:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print("alembic_version:", ver)
        except Exception as e:
            print("alembic_version ERROR:", e)

        rows = conn.execute(
            text(
                """
                SELECT customer_phone_e164, block_type, active, reason, created_at
                FROM customer_blocks
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY created_at DESC
                """
            ),
            {"cid": cid},
        ).all()
        print("\n=== customer_blocks rows ===")
        if not rows:
            print("(none — run manage_customer_block.py --add)")
        for r in rows:
            print(r)

        hit = lookup_customer_block(conn, client_id=cid, customer_phone_e164=phone)
        print(f"\nlookup_customer_block({phone!r}):", hit)

    if not hit:
        print("\nFAIL: no active block for normalized phone — gateway will NOT handoff.")
        return 1
    print("\nOK: block active; gateway should", policy.blocklist_mode, "this number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
