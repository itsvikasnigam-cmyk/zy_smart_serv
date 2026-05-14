"""
Cron-style rollups into ``metrics_daily_client``, ``metrics_daily_agent``,
and ``metrics_hourly_system``. Recomputes **recent UTC windows** idempotently
(INSERT .. ON CONFLICT DO UPDATE) so late-arriving rows are reflected.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.config import settings
from backend.shared.db import engine

log = logging.getLogger("metrics_rollup_worker")


def _utc_days(n: int) -> list[date]:
    today = datetime.now(timezone.utc).date()
    return [today - timedelta(days=i) for i in range(n)]


def _utc_hour_buckets(n_hours: int) -> list[datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0)
    return [start - timedelta(hours=i) for i in range(n_hours)]


def rollup_daily_clients(conn: Connection, days: list[date]) -> None:
    for d in days:
        conn.execute(
            text(
                """
                INSERT INTO metrics_daily_client (
                  client_id, metric_date,
                  customer_messages, ai_messages, agent_messages, system_messages,
                  updated_at
                )
                SELECT
                  ic.client_id,
                  (timezone('utc', m.timestamp))::date AS d,
                  COUNT(*) FILTER (WHERE m.direction = 'in' AND m.sender = 'customer')::int,
                  COUNT(*) FILTER (WHERE m.direction = 'out' AND m.sender = 'ai')::int,
                  COUNT(*) FILTER (WHERE m.direction = 'out' AND m.sender = 'agent')::int,
                  COUNT(*) FILTER (WHERE m.direction = 'out' AND m.sender NOT IN ('ai','agent'))::int,
                  now()
                FROM inbox_messages m
                INNER JOIN inbox_chats ic ON ic.id = m.chat_id
                WHERE (timezone('utc', m.timestamp))::date = :d
                GROUP BY ic.client_id, d
                ON CONFLICT (client_id, metric_date) DO UPDATE SET
                  customer_messages = EXCLUDED.customer_messages,
                  ai_messages = EXCLUDED.ai_messages,
                  agent_messages = EXCLUDED.agent_messages,
                  system_messages = EXCLUDED.system_messages,
                  updated_at = now()
                """
            ),
            {"d": d},
        )


def rollup_daily_agents(conn: Connection, days: list[date]) -> None:
    for d in days:
        conn.execute(
            text(
                """
                INSERT INTO metrics_daily_agent (
                  client_id, agent_user_id, metric_date, replies_count, updated_at
                )
                SELECT
                  ic.client_id,
                  CAST(m.meta_payload->>'by_user_id' AS uuid) AS agent_uid,
                  (timezone('utc', m.timestamp))::date AS d,
                  COUNT(*)::int,
                  now()
                FROM inbox_messages m
                INNER JOIN inbox_chats ic ON ic.id = m.chat_id
                WHERE m.direction = 'out'
                  AND m.sender = 'agent'
                  AND m.meta_payload ? 'by_user_id'
                  AND (timezone('utc', m.timestamp))::date = :d
                GROUP BY ic.client_id, agent_uid, d
                ON CONFLICT (client_id, agent_user_id, metric_date) DO UPDATE SET
                  replies_count = EXCLUDED.replies_count,
                  updated_at = now()
                """
            ),
            {"d": d},
        )


def rollup_hourly_system(conn: Connection, hours: list[datetime]) -> None:
    for hb in hours:
        conn.execute(
            text(
                """
                INSERT INTO metrics_hourly_system (
                  hour_bucket_utc,
                  customer_in_messages,
                  ai_out_messages,
                  agent_out_messages,
                  wa_outbox_rows_created,
                  wa_outbox_rows_dead,
                  updated_at
                )
                SELECT
                  CAST(:hb AS timestamptz),
                  COALESCE((
                    SELECT COUNT(*)::int FROM inbox_messages m
                    WHERE m.direction = 'in' AND m.sender = 'customer'
                      AND date_trunc('hour', timezone('utc', m.timestamp)) = CAST(:hb AS timestamptz)
                  ), 0),
                  COALESCE((
                    SELECT COUNT(*)::int FROM inbox_messages m
                    WHERE m.direction = 'out' AND m.sender = 'ai'
                      AND date_trunc('hour', timezone('utc', m.timestamp)) = CAST(:hb AS timestamptz)
                  ), 0),
                  COALESCE((
                    SELECT COUNT(*)::int FROM inbox_messages m
                    WHERE m.direction = 'out' AND m.sender = 'agent'
                      AND date_trunc('hour', timezone('utc', m.timestamp)) = CAST(:hb AS timestamptz)
                  ), 0),
                  COALESCE((
                    SELECT COUNT(*)::int FROM wa_outbox o
                    WHERE date_trunc('hour', timezone('utc', o.created_at)) = CAST(:hb AS timestamptz)
                  ), 0),
                  COALESCE((
                    SELECT COUNT(*)::int FROM wa_outbox o
                    WHERE o.status = 'DEAD'
                      AND date_trunc('hour', timezone('utc', o.created_at)) = CAST(:hb AS timestamptz)
                  ), 0),
                  now()
                ON CONFLICT (hour_bucket_utc) DO UPDATE SET
                  customer_in_messages = EXCLUDED.customer_in_messages,
                  ai_out_messages = EXCLUDED.ai_out_messages,
                  agent_out_messages = EXCLUDED.agent_out_messages,
                  wa_outbox_rows_created = EXCLUDED.wa_outbox_rows_created,
                  wa_outbox_rows_dead = EXCLUDED.wa_outbox_rows_dead,
                  updated_at = now()
                """
            ),
            {"hb": hb},
        )


def run_once() -> None:
    days = _utc_days(settings.metrics_rollup_lookback_days)
    hours = _utc_hour_buckets(settings.metrics_rollup_hourly_lookback)
    with engine.begin() as conn:
        rollup_daily_clients(conn, days)
        rollup_daily_agents(conn, days)
        rollup_hourly_system(conn, hours)
    log.info(
        "metrics rollup ok (daily days=%s hourly buckets=%s)",
        len(days),
        len(hours),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("metrics_rollup_worker started (interval=%ss)", settings.metrics_rollup_sleep_seconds)
    while True:
        try:
            run_once()
        except Exception:
            log.exception("metrics_rollup_worker loop error")
        time.sleep(settings.metrics_rollup_sleep_seconds)


if __name__ == "__main__":
    main()
