from __future__ import annotations

"""Print tenant (api_clients) IDs for copy-paste into the Flutter super-admin app.

Usage (from repo root):

    $env:PYTHONPATH = (Get-Location).Path
    $env:DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/zysmart"
    python backend/tools/list_tenants.py
"""

import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id::text, COALESCE(business_name, '(no name)') AS name,
                       COALESCE(entitlement_plan, '?') AS plan
                FROM api_clients
                ORDER BY created_at ASC
                """
            )
        ).all()

    if not rows:
        print("No tenants found in api_clients.")
        print("Run dev_seed.py first, or create a client in your database.")
        return 1

    print("")
    print("=== Tenants in your database (copy ONE id for Flutter Broadcast) ===")
    print("")
    for i, (cid, name, plan) in enumerate(rows, start=1):
        print(f"  {i}. Business: {name}")
        print(f"     Plan:     {plan}")
        print(f"     ID:       {cid}")
        print("")
    print("In the app: link icon -> super_admin tenant client_id -> paste the ID line.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
