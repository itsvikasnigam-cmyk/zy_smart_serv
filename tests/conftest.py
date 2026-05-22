"""Pytest hooks for the ``tests/`` package."""

from __future__ import annotations

import os

# GitHub Actions may set DATABASE_URL="" which breaks SQLAlchemy URL parsing on import.
# Use the same default credentials as Settings (CI has no Postgres; unit tests mock DB).
if not (os.environ.get("DATABASE_URL") or "").strip():
    os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/zysmart"

# Optional Postgres integration (Chat N): keep default ``python -m pytest tests/`` output
# free of extra skips — omit the module unless explicitly enabled + DATABASE_URL set.
if not (
    os.environ.get("RUN_POSTGRES_INTEGRATION") == "1"
    and os.environ.get("DATABASE_URL", "").strip()
):
    collect_ignore = ["test_postgres_integration_optional.py"]
