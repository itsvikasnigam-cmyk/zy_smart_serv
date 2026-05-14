"""
Increment ``bill_usage_daily`` from ``inbox_messages`` (cursor-based), and set
soft/hard threshold timestamps when inbound customer message counts cross
``ops_runtime_config.usage.daily_inbound_limits`` for the client's entitlement.

Chat B (M2 gateway paywall) should **not** import this module; see HANDOFF.md
for the read interface (SQL + config key).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import text

from backend.shared.config import settings
from backend.shared.db import engine
from backend.workers.usage_metrics_common import (
    CURSOR_KEY_INBOX_MESSAGES,
    load_daily_inbound_limits_json,
    plan_soft_hard,
    should_mark_hard,
    should_mark_soft,
    utc_calendar_date,
)

log = logging.getLogger("usage_increment_worker")


def _fetch_cursor(conn: Any) -> tuple[Any, Any]:
    row = conn.execute(
        text(
            """
            SELECT cursor_timestamp, cursor_message_id
            FROM worker_usage_cursors
            WHERE worker_key = :k
            """
        ),
        {"k": CURSOR_KEY_INBOX_MESSAGES},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing worker_usage_cursors row for {CURSOR_KEY_INBOX_MESSAGES!r}")
    return row[0], row[1]


def _update_cursor(conn: Any, ts: Any, mid: Any) -> None:
    conn.execute(
        text(
            """
            UPDATE worker_usage_cursors
            SET cursor_timestamp = :ts, cursor_message_id = CAST(:mid AS uuid)
            WHERE worker_key = :k
            """
        ),
        {"ts": ts, "mid": str(mid), "k": CURSOR_KEY_INBOX_MESSAGES},
    )


def _apply_thresholds_for_clients(
    conn: Any, *, limits: dict[str, Any], pairs: set[tuple[Any, date]]
) -> None:
    if not pairs:
        return
    for client_id, usage_date in pairs:
        row = conn.execute(
            text(
                """
                SELECT bud.inbound_customer_messages, ac.entitlement_plan,
                       bud.soft_threshold_crossed_at, bud.hard_threshold_crossed_at
                FROM bill_usage_daily bud
                JOIN api_clients ac ON ac.id = bud.client_id
                WHERE bud.client_id = CAST(:cid AS uuid) AND bud.usage_date = :udate
                """
            ),
            {"cid": str(client_id), "udate": usage_date},
        ).fetchone()
        if not row:
            continue
        inbound, plan, soft_at, hard_at = int(row[0]), row[1], row[2], row[3]
        soft_n, hard_n = plan_soft_hard(limits, (plan or "trial"))
        set_soft = should_mark_soft(inbound, soft_n) and soft_at is None
        set_hard = should_mark_hard(inbound, hard_n) and hard_at is None
        if not set_soft and not set_hard:
            continue
        conn.execute(
            text(
                """
                UPDATE bill_usage_daily
                SET soft_threshold_crossed_at = CASE WHEN :set_soft THEN COALESCE(soft_threshold_crossed_at, now())
                                                      ELSE soft_threshold_crossed_at END,
                    hard_threshold_crossed_at = CASE WHEN :set_hard THEN COALESCE(hard_threshold_crossed_at, now())
                                                      ELSE hard_threshold_crossed_at END,
                    updated_at = now()
                WHERE client_id = CAST(:cid AS uuid) AND usage_date = :udate
                """
            ),
            {"cid": str(client_id), "udate": usage_date, "set_soft": set_soft, "set_hard": set_hard},
        )


def run_once() -> int:
    """Returns number of inbox_messages rows applied to aggregates (0 if idle)."""
    batch = settings.usage_worker_batch_size
    processed_rows = 0

    with engine.begin() as conn:
        limits = load_daily_inbound_limits_json(conn)
        cur_ts, cur_id = _fetch_cursor(conn)

        rows = conn.execute(
            text(
                """
                SELECT m.id, m.timestamp, m.direction, m.sender, ic.client_id
                FROM inbox_messages m
                INNER JOIN inbox_chats ic ON ic.id = m.chat_id
                WHERE (m.timestamp > :cts)
                   OR (m.timestamp = :cts AND m.id > CAST(:cid AS uuid))
                ORDER BY m.timestamp ASC, m.id ASC
                LIMIT :lim
                """
            ),
            {"cts": cur_ts, "cid": str(cur_id), "lim": batch},
        ).all()

        if not rows:
            return 0

        # (client_id, usage_date) -> counters
        deltas: dict[tuple[Any, date], dict[str, int]] = defaultdict(
            lambda: {
                "inbound_customer_messages": 0,
                "outbound_ai_messages": 0,
                "outbound_agent_messages": 0,
                "outbound_system_messages": 0,
            }
        )
        last_ts, last_id = cur_ts, cur_id
        affected: set[tuple[Any, date]] = set()

        for mid, ts, direction, sender, client_id in rows:
            last_ts, last_id = ts, mid
            processed_rows += 1
            uday = utc_calendar_date(ts)
            key = (client_id, uday)
            d = deltas[key]
            if direction == "in" and sender == "customer":
                d["inbound_customer_messages"] += 1
            elif direction == "out":
                if sender == "ai":
                    d["outbound_ai_messages"] += 1
                elif sender == "agent":
                    d["outbound_agent_messages"] += 1
                else:
                    d["outbound_system_messages"] += 1

        for (cid, uday), d in deltas.items():
            affected.add((cid, uday))
            conn.execute(
                text(
                    """
                    INSERT INTO bill_usage_daily (
                      client_id, usage_date,
                      inbound_customer_messages,
                      outbound_ai_messages, outbound_agent_messages, outbound_system_messages,
                      updated_at
                    )
                    VALUES (
                      CAST(:cid AS uuid), :udate,
                      :inc_in, :inc_ai, :inc_ag, :inc_sy, now()
                    )
                    ON CONFLICT (client_id, usage_date) DO UPDATE SET
                      inbound_customer_messages = bill_usage_daily.inbound_customer_messages + EXCLUDED.inbound_customer_messages,
                      outbound_ai_messages = bill_usage_daily.outbound_ai_messages + EXCLUDED.outbound_ai_messages,
                      outbound_agent_messages = bill_usage_daily.outbound_agent_messages + EXCLUDED.outbound_agent_messages,
                      outbound_system_messages = bill_usage_daily.outbound_system_messages + EXCLUDED.outbound_system_messages,
                      updated_at = now()
                    """
                ),
                {
                    "cid": str(cid),
                    "udate": uday,
                    "inc_in": d["inbound_customer_messages"],
                    "inc_ai": d["outbound_ai_messages"],
                    "inc_ag": d["outbound_agent_messages"],
                    "inc_sy": d["outbound_system_messages"],
                },
            )

        _update_cursor(conn, last_ts, last_id)
        _apply_thresholds_for_clients(conn, limits=limits, pairs=affected)

    if processed_rows:
        log.info("Applied %s inbox_messages rows to bill_usage_daily", processed_rows)
    return processed_rows


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info(
        "usage_increment_worker started (batch_size=%s sleep=%ss)",
        settings.usage_worker_batch_size,
        settings.usage_worker_sleep_seconds,
    )
    while True:
        try:
            run_once()
        except Exception:
            log.exception("usage_increment_worker loop error")
        time.sleep(settings.usage_worker_sleep_seconds)


if __name__ == "__main__":
    main()
