"""Print ops_releases columns and constraints (Chat Z debug).

Usage:
  python backend/tools/inspect_ops_releases_schema.py
"""

from __future__ import annotations

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.connect() as conn:
        cols = conn.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'ops_releases'
                ORDER BY ordinal_position
                """
            )
        ).all()
        checks = conn.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'ops_releases' AND c.contype = 'c'
                """
            )
        ).all()
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print("alembic_version:", ver)
    print("\n=== ops_releases columns ===")
    for c in cols or []:
        print(f"  {c[0]:30} {c[1]:20} nullable={c[2]}")
    print("\n=== CHECK constraints ===")
    for r in checks or []:
        print(f"  {r[0]}: {r[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
