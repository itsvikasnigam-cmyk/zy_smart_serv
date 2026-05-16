from __future__ import annotations

"""One-command dev login setup — no need to copy tenant UUID manually.

Creates/resets passwords for owner, agent, and super_admin on the first tenant
in api_clients (or --client-id if you pass one).

Usage (from repo root):

    cd C:\\Users\\TV_Station\\.cursor\\projects\\empty-window
    $env:PYTHONPATH = (Get-Location).Path
    $env:DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/zysmart"
    python backend/tools/setup_dev_logins.py
"""

import argparse
import sys

from sqlalchemy import text

from backend.apps.client_api.auth import hash_password, verify_password
from backend.shared.db import engine


def _first_client_id(conn) -> str | None:
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
    return row[0] if row else None


def _reset_email(conn, *, email: str, password: str, role: str, client_id: str) -> int:
    """Update password for every row with this email; insert if missing."""
    email_norm = email.strip().lower()
    pw_hash = hash_password(password)
    rows = conn.execute(
        text(
            """
            SELECT id::text FROM api_users
            WHERE lower(email) = :email
            """
        ),
        {"email": email_norm},
    ).all()
    updated = 0
    for (uid,) in rows:
        conn.execute(
            text(
                """
                UPDATE api_users
                SET password_hash = :pw,
                    role = :role,
                    client_id = CAST(:cid AS uuid)
                WHERE id = CAST(:uid AS uuid)
                """
            ),
            {"pw": pw_hash, "role": role, "cid": client_id, "uid": uid},
        )
        updated += 1
    if updated == 0:
        conn.execute(
            text(
                """
                INSERT INTO api_users (client_id, name, email, role, password_hash)
                VALUES (CAST(:cid AS uuid), :name, :email, :role, :pw)
                """
            ),
            {
                "cid": client_id,
                "name": role.replace("_", " ").title(),
                "email": email_norm,
                "role": role,
                "pw": pw_hash,
            },
        )
        updated = 1
    # Verify
    check = conn.execute(
        text("SELECT password_hash FROM api_users WHERE lower(email) = :email LIMIT 1"),
        {"email": email_norm},
    ).fetchone()
    if not check or not verify_password(password, check[0]):
        raise RuntimeError(f"password verify failed after reset for {email_norm}")
    return updated


def main() -> int:
    p = argparse.ArgumentParser(description="Reset dev login passwords (beginner-friendly).")
    p.add_argument(
        "--client-id",
        default="",
        help="Optional tenant UUID. If omitted, uses the first api_clients row.",
    )
    args = p.parse_args()

    with engine.begin() as conn:
        cid = (args.client_id or "").strip() or _first_client_id(conn)
        if not cid:
            print("ERROR: No tenant in api_clients. Run dev_seed.py first.", file=sys.stderr)
            return 1
        name_row = conn.execute(
            text("SELECT COALESCE(business_name, '(no name)') FROM api_clients WHERE id = CAST(:c AS uuid)"),
            {"c": cid},
        ).fetchone()
        biz = name_row[0] if name_row else "?"

        accounts = [
            ("owner1@example.com", "Owner!2026", "owner"),
            ("agent1@example.com", "Agent!2026", "agent"),
            ("admin@example.com", "Admin!2026", "super_admin"),
        ]
        print("")
        print("=== Dev logins reset ===")
        print(f"Tenant: {biz}")
        print(f"ID:     {cid}")
        print("")
        for email, password, role in accounts:
            n = _reset_email(conn, email=email, password=password, role=role, client_id=cid)
            extra = f" ({n} DB rows updated)" if n > 1 else ""
            print(f"  {role:12}  email: {email:22}  password: {password}{extra}")
        print("")
        print("In Flutter: use these emails/passwords on Sign in.")
        print("Super admin -> SOPs/Dash/Broadcast tabs.")
        print("Owner/Agent -> Inbox/Dashboard/Account tabs.")
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
