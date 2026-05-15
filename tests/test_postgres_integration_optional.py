"""
Postgres-backed integration checks for Chat K workers (and minimal schema sanity).

Collected only when ``RUN_POSTGRES_INTEGRATION=1`` and ``DATABASE_URL`` are set
(see ``tests/conftest.py``); otherwise the module is omitted from the default
``python -m pytest tests/`` run so the suite does not gain extra skips.

**Prerequisites:** migrations at head on the target database (``alembic upgrade head``).
Use a disposable local database; the usage worker advances ``worker_usage_cursors``
based on real ``inbox_messages`` rows — this suite watermarks the cursor to the
current table tail before inserting fixtures so existing data is not reprocessed.

Manual run (PowerShell, repo root):

    $env:PYTHONPATH="$PWD"
    $env:DATABASE_URL="<same URL you use for alembic; example often postgres/postgres>"
    $env:RUN_POSTGRES_INTEGRATION="1"
    python -m pytest tests/test_postgres_integration_optional.py -v

Covers: ``usage_increment_worker.run_once``, ``metrics_rollup_worker.run_once`` (including
``metrics_hourly_system`` for the current UTC hour), Chat K public tables, and minimal
``ops_*`` presence — requires **Alembic at head** (``0005`` + ``0010`` columns on
``metrics_hourly_system`` used by the rollup SQL).

If login fails (e.g. ``FATAL: password authentication failed``), the suite **skips** with a
short hint instead of failing three reds — fix ``DATABASE_URL`` (env overrides repo
``.env`` for this field in pydantic-settings) and re-run.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.workers.usage_metrics_common import CURSOR_KEY_INBOX_MESSAGES


def _pg_integration_enabled() -> bool:
    return os.environ.get("RUN_POSTGRES_INTEGRATION") == "1" and bool(
        os.environ.get("DATABASE_URL", "").strip()
    )


@pytest.fixture(scope="module", autouse=True)
def _pg_integration_skip_if_db_unreachable() -> None:
    """Avoid three hard failures when Postgres is down or credentials do not match."""
    if not _pg_integration_enabled():
        return
    from backend.shared.db import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        detail = str(getattr(exc, "orig", None) or exc)
        pytest.skip(
            "Postgres unreachable with current DATABASE_URL — use the same URL that "
            "works for `alembic upgrade head` (password in URL must match your server; "
            "URL-encode special characters). "
            f"Driver said: {detail}"
        )


@pytest.mark.skipif(
    not _pg_integration_enabled(),
    reason="Set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL (see module docstring).",
)
def test_usage_increment_worker_updates_bill_usage_daily() -> None:
    from backend.workers.usage_increment_worker import run_once

    from backend.shared.db import engine

    client_id = uuid4()
    chat_id = uuid4()
    m1, m2 = uuid4(), uuid4()

    with engine.begin() as conn:
        saved = conn.execute(
            text(
                """
                SELECT cursor_timestamp, cursor_message_id
                FROM worker_usage_cursors
                WHERE worker_key = :k
                """
            ),
            {"k": CURSOR_KEY_INBOX_MESSAGES},
        ).fetchone()
        assert saved is not None, "worker_usage_cursors row missing (run migrations)"
        orig_ts, orig_mid = saved[0], saved[1]

        top = conn.execute(
            text(
                """
                SELECT m.timestamp, m.id
                FROM inbox_messages m
                ORDER BY m.timestamp DESC, m.id DESC
                LIMIT 1
                """
            )
        ).fetchone()
        if top:
            conn.execute(
                text(
                    """
                    UPDATE worker_usage_cursors
                    SET cursor_timestamp = :ts, cursor_message_id = CAST(:mid AS uuid)
                    WHERE worker_key = :k
                    """
                ),
                {"ts": top[0], "mid": str(top[1]), "k": CURSOR_KEY_INBOX_MESSAGES},
            )
            tail_ts = top[0]
            if getattr(tail_ts, "tzinfo", None) is None:
                tail_ts = tail_ts.replace(tzinfo=timezone.utc)
            ts1 = tail_ts + timedelta(seconds=1)
        else:
            ts1 = datetime.now(timezone.utc)
        ts2 = ts1 + timedelta(seconds=2)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO api_clients (id, business_name, entitlement_plan)
                    VALUES (CAST(:id AS uuid), 'pytest_pg_integration', 'trial')
                    """
                ),
                {"id": str(client_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO inbox_chats (id, client_id, customer_phone, state)
                    VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), '+19999990001', 'AI_ACTIVE')
                    """
                ),
                {"id": str(chat_id), "cid": str(client_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO inbox_messages
                      (id, chat_id, direction, sender, text, timestamp, meta_msg_id)
                    VALUES
                      (CAST(:m1 AS uuid), CAST(:chat AS uuid), 'in', 'customer', 'a',
                       CAST(:ts1 AS timestamptz), NULL),
                      (CAST(:m2 AS uuid), CAST(:chat AS uuid), 'in', 'customer', 'b',
                       CAST(:ts2 AS timestamptz), NULL)
                    """
                ),
                {
                    "m1": str(m1),
                    "m2": str(m2),
                    "chat": str(chat_id),
                    "ts1": ts1,
                    "ts2": ts2,
                },
            )

        n = run_once()
        assert n >= 2

        uday = ts1.astimezone(timezone.utc).date()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT inbound_customer_messages
                    FROM bill_usage_daily
                    WHERE client_id = CAST(:cid AS uuid) AND usage_date = :ud
                    """
                ),
                {"cid": str(client_id), "ud": uday},
            ).fetchone()
        assert row is not None
        assert int(row[0]) >= 2
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM api_clients WHERE id = CAST(:id AS uuid)"),
                {"id": str(client_id)},
            )
            conn.execute(
                text(
                    """
                    UPDATE worker_usage_cursors
                    SET cursor_timestamp = :ts, cursor_message_id = CAST(:mid AS uuid)
                    WHERE worker_key = :k
                    """
                ),
                {"ts": orig_ts, "mid": str(orig_mid), "k": CURSOR_KEY_INBOX_MESSAGES},
            )


@pytest.mark.skipif(
    not _pg_integration_enabled(),
    reason="Set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL (see module docstring).",
)
def test_metrics_rollup_worker_inserts_metrics_rows() -> None:
    from backend.workers.metrics_rollup_worker import run_once as metrics_run_once

    from backend.shared.db import engine

    client_id = uuid4()
    chat_id = uuid4()
    mid = uuid4()
    ts = datetime.now(timezone.utc)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO api_clients (id, business_name, entitlement_plan)
                VALUES (CAST(:id AS uuid), 'pytest_pg_metrics', 'trial')
                """
            ),
            {"id": str(client_id)},
        )
        conn.execute(
            text(
                """
                INSERT INTO inbox_chats (id, client_id, customer_phone, state)
                VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), '+19999990002', 'AI_ACTIVE')
                """
            ),
            {"id": str(chat_id), "cid": str(client_id)},
        )
        conn.execute(
            text(
                """
                INSERT INTO inbox_messages
                  (id, chat_id, direction, sender, text, timestamp, meta_msg_id)
                VALUES
                  (CAST(:m AS uuid), CAST(:chat AS uuid), 'in', 'customer', 'rollup',
                   CAST(:ts AS timestamptz), NULL)
                """
            ),
            {"m": str(mid), "chat": str(chat_id), "ts": ts},
        )

    try:
        metrics_run_once()
        mday = ts.astimezone(timezone.utc).date()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT customer_messages
                    FROM metrics_daily_client
                    WHERE client_id = CAST(:cid AS uuid) AND metric_date = :d
                    """
                ),
                {"cid": str(client_id), "d": mday},
            ).fetchone()
        assert row is not None
        assert int(row[0]) >= 1
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM api_clients WHERE id = CAST(:id AS uuid)"),
                {"id": str(client_id)},
            )


@pytest.mark.skipif(
    not _pg_integration_enabled(),
    reason="Set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL (see module docstring).",
)
def test_ops_sops_table_present_when_migrated() -> None:
    """Lightweight sanity check that Alembic ``0006_ops_sops`` objects exist."""
    from backend.shared.db import engine

    with engine.connect() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN ('ops_sops', 'ops_sop_versions', 'ops_run_logs')
                """
            )
        ).scalar()
    assert int(n or 0) == 3, "expected ops_api tables after upgrade head (0006_ops_sops)"


@pytest.mark.skipif(
    not _pg_integration_enabled(),
    reason="Set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL (see module docstring).",
)
def test_chat_k_public_tables_present() -> None:
    """Alembic ``0005_usage_metrics`` core objects exist (fail fast if DB is behind head)."""
    from backend.shared.db import engine

    names = (
        "bill_usage_daily",
        "metrics_daily_client",
        "metrics_daily_agent",
        "metrics_hourly_system",
        "worker_usage_cursors",
    )
    with engine.connect() as conn:
        for tbl in names:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :name
                    """
                ),
                {"name": tbl},
            ).fetchone()
            assert row is not None, f"missing public table {tbl!r} (run alembic upgrade head)"


@pytest.mark.skipif(
    not _pg_integration_enabled(),
    reason="Set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL (see module docstring).",
)
def test_metrics_hourly_system_inserts_current_utc_hour_bucket() -> None:
    """``metrics_rollup_worker.run_once`` upserts a row for the truncated current UTC hour."""
    from backend.workers.metrics_rollup_worker import run_once as metrics_run_once

    from backend.shared.db import engine

    metrics_run_once()
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT customer_in_messages, wa_outbox_rows_created
                FROM metrics_hourly_system
                WHERE hour_bucket_utc = CAST(:h AS timestamptz)
                """
            ),
            {"h": hour},
        ).fetchone()
    assert row is not None, "metrics_hourly_system missing row for current UTC hour after rollup"
