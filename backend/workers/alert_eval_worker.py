"""
M7: evaluate simple spike thresholds → ``ops_alert_events`` rows + structured logging.

Paging / ``ops_api`` auto-runs (M9 phase 2) stay out of this worker — see HANDOFF coordination with Chat I.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

from backend.shared.config import settings
from backend.shared.db import engine
from backend.shared.ops_alerts import insert_ops_alert_event
from backend.shared.ops_sop_auto_trigger import maybe_create_auto_sop_run

log = logging.getLogger("alert_eval_worker")

ALERT_THRESHOLDS_KEY = "alerts.thresholds"

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "outbox_dead_spike_window_minutes": 15,
    "outbox_dead_spike_min_count": 5,
    "meta_webhook_errors_spike_window_minutes": 60,
    "meta_webhook_errors_spike_min_count": 50,
}


def _merge_thresholds(raw: Any | None) -> dict[str, Any]:
    out = dict(DEFAULT_THRESHOLDS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[k] = v
    return out


def _load_thresholds(conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": ALERT_THRESHOLDS_KEY},
    ).fetchone()
    if not row:
        return dict(DEFAULT_THRESHOLDS)
    return _merge_thresholds(row[0])


def _window_floor_key(now: datetime, *, window_minutes: int) -> str:
    epoch = int(now.timestamp())
    step = max(60, int(window_minutes) * 60)
    floored = epoch - (epoch % step)
    return datetime.fromtimestamp(floored, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def run_once() -> None:
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        th = _load_thresholds(conn)

        dead_m = int(th.get("outbox_dead_spike_window_minutes") or 15)
        dead_min = int(th.get("outbox_dead_spike_min_count") or 5)
        dead_cnt = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM wa_outbox
                    WHERE status = 'DEAD'
                      AND COALESCE(dead_at, created_at) >= (timezone('utc', now()) - (:m || ' minutes')::interval)
                    """
                ),
                {"m": dead_m},
            ).scalar_one()
            or 0
        )
        if dead_cnt >= dead_min:
            slot = _window_floor_key(now, window_minutes=dead_m)
            dk = f"outbox_dead_spike:{slot}"
            inserted, event_id = insert_ops_alert_event(
                conn,
                alert_type="OUTBOX_DEAD_SPIKE",
                severity="error",
                summary=f"DEAD outbox rows >= {dead_min} in last {dead_m}m (observed {dead_cnt})",
                detail={"count": dead_cnt, "window_minutes": dead_m},
                dedupe_key=dk,
            )
            if inserted:
                log.error("alert OUTBOX_DEAD_SPIKE count=%s window_min=%s", dead_cnt, dead_m)
                maybe_create_auto_sop_run(
                    conn,
                    alert_type="OUTBOX_DEAD_SPIKE",
                    ops_alert_event_id=event_id,
                    detail={"count": dead_cnt, "window_minutes": dead_m},
                )

        meta_m = int(th.get("meta_webhook_errors_spike_window_minutes") or 60)
        meta_min = int(th.get("meta_webhook_errors_spike_min_count") or 50)
        try:
            meta_cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::int FROM wa_meta_webhook_errors
                        WHERE received_at >= (timezone('utc', now()) - (:m || ' minutes')::interval)
                        """
                    ),
                    {"m": meta_m},
                ).scalar_one()
                or 0
            )
        except ProgrammingError:
            log.debug("meta webhook error count query skipped", exc_info=True)
            meta_cnt = 0
        if meta_cnt >= meta_min:
            slot = _window_floor_key(now, window_minutes=meta_m)
            dk = f"meta_webhook_errors_spike:{slot}"
            inserted, event_id = insert_ops_alert_event(
                conn,
                alert_type="META_WEBHOOK_ERROR_SPIKE",
                severity="warning",
                summary=f"Meta webhook error rows >= {meta_min} in last {meta_m}m (observed {meta_cnt})",
                detail={"count": meta_cnt, "window_minutes": meta_m},
                dedupe_key=dk,
            )
            if inserted:
                log.error("alert META_WEBHOOK_ERROR_SPIKE count=%s window_min=%s", meta_cnt, meta_m)
                maybe_create_auto_sop_run(
                    conn,
                    alert_type="META_WEBHOOK_ERROR_SPIKE",
                    ops_alert_event_id=event_id,
                    detail={"count": meta_cnt, "window_minutes": meta_m},
                )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("alert_eval_worker started (interval=%ss)", settings.alert_eval_worker_sleep_seconds)
    while True:
        try:
            run_once()
        except Exception:
            log.exception("alert_eval_worker tick error")
        time.sleep(settings.alert_eval_worker_sleep_seconds)


if __name__ == "__main__":
    main()
