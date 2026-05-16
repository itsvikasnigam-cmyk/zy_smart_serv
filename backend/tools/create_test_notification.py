from __future__ import annotations

"""Create one dev inbox notification for an owner (command-line).

Usage (from repo root):

    $env:PYTHONPATH = (Get-Location).Path
    $env:DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/zysmart"
    python backend/tools/create_test_notification.py --email owner1@example.com
"""

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.inbox_notify import insert_notification


def main() -> int:
    p = argparse.ArgumentParser(description="Insert a dev test inbox notification.")
    p.add_argument(
        "--email",
        default="owner1@example.com",
        help="Recipient user email (default: owner1@example.com)",
    )
    args = p.parse_args()
    email = args.email.strip().lower()

    with engine.begin() as conn:
        user = conn.execute(
            text(
                """
                SELECT id::text, client_id::text, role
                FROM api_users
                WHERE lower(email) = :email
                LIMIT 1
                """
            ),
            {"email": email},
        ).fetchone()
        if not user:
            print(f"ERROR: No user with email {email}", file=sys.stderr)
            return 1
        uid, cid, role = user[0], user[1], user[2]
        if not cid:
            print(f"ERROR: User {email} has no client_id (super_admin needs --email of owner)", file=sys.stderr)
            return 1
        chat = conn.execute(
            text(
                """
                SELECT id::text FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"cid": cid},
        ).fetchone()
        chat_id = chat[0] if chat else None
        nid, _ = insert_notification(
            conn,
            client_id=cid,
            recipient_user_id=uid,
            chat_id=chat_id,
            kind="dev_test",
            title="Test alert (dev)",
            body="Created from backend/tools/create_test_notification.py",
            payload={"dev": True},
        )

    print("")
    print("=== Test notification created ===")
    print(f"  User:   {email} ({role})")
    print(f"  ID:     {nid}")
    print(f"  Chat:   {chat_id or '(none)'}")
    print("")
    print("In the app: log in as that user -> Alerts -> Refresh list")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
