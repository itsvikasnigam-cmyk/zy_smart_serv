from __future__ import annotations

"""Seed an owner + agent user for the client_api smoke flow.

Idempotent: re-running updates the password hash for existing emails.

Usage:
    python backend/tools/dev_seed_users.py --client-id <CLIENT_UUID> \
        [--owner-email owner1@example.com] [--owner-password Owner!2026] \
        [--agent-email agent1@example.com] [--agent-password Agent!2026] \
        [--super-admin-email admin@example.com] [--super-admin-password Admin!2026]

Optional ``--super-admin-email`` upserts a ``super_admin`` on the same ``client_id`` (for
``dev_ops_api_smoke.py`` and Flutter super-admin against ``ops_api``).

Prints user ids and credentials so other scripts can pick them up.
"""

import argparse
import sys

from sqlalchemy import text

from backend.apps.client_api.auth import hash_password
from backend.shared.db import engine


def upsert_user(conn, *, client_id: str, name: str, email: str, role: str, password: str) -> str:
    pw_hash = hash_password(password)
    row = conn.execute(
        text(
            """
            INSERT INTO api_users (client_id, name, email, role, password_hash)
            VALUES (CAST(:cid AS uuid), :name, :email, :role, :pw)
            ON CONFLICT DO NOTHING
            RETURNING id::text
            """
        ),
        {"cid": client_id, "name": name, "email": email, "role": role, "pw": pw_hash},
    ).fetchone()
    if row:
        return row[0]
    # Existed: update password + role + name + client.
    row = conn.execute(
        text(
            """
            UPDATE api_users
            SET name = :name,
                role = :role,
                client_id = CAST(:cid AS uuid),
                password_hash = :pw
            WHERE lower(email) = lower(:email)
            RETURNING id::text
            """
        ),
        {"cid": client_id, "name": name, "email": email, "role": role, "pw": pw_hash},
    ).fetchone()
    if not row:
        raise RuntimeError(f"failed to upsert user {email}")
    return row[0]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", required=True, help="api_clients.id to attach users to")
    p.add_argument("--owner-email", default="owner1@example.com")
    p.add_argument("--owner-password", default="Owner!2026")
    p.add_argument("--agent-email", default="agent1@example.com")
    p.add_argument("--agent-password", default="Agent!2026")
    p.add_argument(
        "--super-admin-email",
        default="",
        help="If set, also upsert a super_admin user on the same client_id (for ops_api smoke).",
    )
    p.add_argument("--super-admin-password", default="Admin!2026")
    args = p.parse_args()

    with engine.begin() as conn:
        chk = conn.execute(
            text("SELECT id::text FROM api_clients WHERE id = CAST(:cid AS uuid) LIMIT 1"),
            {"cid": args.client_id},
        ).fetchone()
        if not chk:
            print(f"client_id not found: {args.client_id}", file=sys.stderr)
            return 2

        owner_id = upsert_user(
            conn,
            client_id=args.client_id,
            name="Owner One",
            email=args.owner_email,
            role="owner",
            password=args.owner_password,
        )
        agent_id = upsert_user(
            conn,
            client_id=args.client_id,
            name="Agent One",
            email=args.agent_email,
            role="agent",
            password=args.agent_password,
        )
        super_admin_id: str | None = None
        if (args.super_admin_email or "").strip():
            super_admin_id = upsert_user(
                conn,
                client_id=args.client_id,
                name="Super Admin",
                email=(args.super_admin_email or "").strip(),
                role="super_admin",
                password=args.super_admin_password,
            )

    print(f"CLIENT_ID={args.client_id}")
    print(f"OWNER_USER_ID={owner_id}")
    print(f"OWNER_EMAIL={args.owner_email}")
    print(f"OWNER_PASSWORD={args.owner_password}")
    print(f"AGENT_USER_ID={agent_id}")
    print(f"AGENT_EMAIL={args.agent_email}")
    print(f"AGENT_PASSWORD={args.agent_password}")
    if super_admin_id:
        print(f"SUPER_ADMIN_USER_ID={super_admin_id}")
        print(f"SUPER_ADMIN_EMAIL={(args.super_admin_email or '').strip()}")
        print(f"SUPER_ADMIN_PASSWORD={args.super_admin_password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
