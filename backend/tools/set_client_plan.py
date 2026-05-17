"""Set api_clients.entitlement_plan for testing trial / paid tiers (dev/staging).

Usage:

    cd ...\\empty-window; . .\\dev-env.ps1
    python backend/tools/list_tenants.py
    python backend/tools/set_client_plan.py --plan trial --trial-days 14
    python backend/tools/set_client_plan.py --plan growth
"""

from __future__ import annotations

import argparse
import re
import sys

from sqlalchemy import text

from backend.shared.db import engine

PLANS = ("trial", "starter", "growth", "pro", "churned")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _resolve_client_id(conn, raw: str | None) -> str:
    cid = (raw or "").strip()
    placeholders = {"", "PASTE_THE_UUID_HERE", "YOUR_CLIENT_ID", "<uuid>"}
    if cid.upper() in {p.upper() for p in placeholders if p} or not _UUID_RE.match(cid):
        row = conn.execute(
            text(
                """
                SELECT id::text, COALESCE(business_name, '(no name)')
                FROM api_clients
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
        ).fetchone()
        if not row:
            print("ERROR: no tenants in api_clients. Run: python backend\\tools\\dev_seed.py ...")
            sys.exit(1)
        print(f"Using first tenant: {row[1]}")
        print(f"  client_id={row[0]}")
        return row[0]
    return cid


def main() -> int:
    p = argparse.ArgumentParser(
        description="Set entitlement plan on a tenant (omit --client-id to use first tenant)."
    )
    p.add_argument(
        "--client-id",
        default="",
        help="Tenant UUID from list_tenants.py (optional: uses first tenant if omitted)",
    )
    p.add_argument("--plan", choices=PLANS, required=True)
    p.add_argument("--trial-days", type=int, default=0, help="If plan=trial, set trial_end to now+N days")
    args = p.parse_args()

    with engine.begin() as conn:
        cid = _resolve_client_id(conn, args.client_id)
        if args.plan == "trial" and args.trial_days > 0:
            conn.execute(
                text(
                    """
                    UPDATE api_clients
                    SET entitlement_plan = 'trial',
                        trial_end = timezone('utc', now()) + (:d || ' days')::interval
                    WHERE id = CAST(:cid AS uuid)
                    """
                ),
                {"cid": cid, "d": args.trial_days},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE api_clients
                    SET entitlement_plan = :plan
                    WHERE id = CAST(:cid AS uuid)
                    """
                ),
                {"cid": cid, "plan": args.plan},
            )
        row = conn.execute(
            text(
                """
                SELECT entitlement_plan::text, trial_end
                FROM api_clients WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": cid},
        ).fetchone()
    if not row:
        print("ERROR: client_id not found")
        return 1
    print(f"OK: client {cid} -> plan={row[0]} trial_end={row[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
