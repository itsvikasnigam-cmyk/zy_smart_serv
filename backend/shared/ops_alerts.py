"""M7: durable alert rows + logging (paging / SOP auto-trigger is phase 2 — see HANDOFF)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("ops_alerts")


def insert_ops_alert_event(
    conn: Connection,
    *,
    alert_type: str,
    severity: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """
    Insert one row into ``ops_alert_events``.

    When ``dedupe_key`` is set, conflicts on the partial unique index are ignored (returns False).
    """
    dk = (dedupe_key or "").strip() or None
    try:
        conn.execute(
            text(
                """
                INSERT INTO ops_alert_events (alert_type, severity, summary, detail_json, dedupe_key)
                VALUES (:t, :s, :sum, CAST(:detail AS jsonb), :dk)
                """
            ),
            {
                "t": alert_type,
                "s": severity,
                "sum": summary[:4000],
                "detail": json.dumps(detail or {}, separators=(",", ":")),
                "dk": dk,
            },
        )
    except IntegrityError:
        return False
    log.warning("ops_alert %s [%s] %s", alert_type, severity, summary)
    return True


def record_alert_event_safe(
    engine: Engine,
    *,
    alert_type: str,
    severity: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> None:
    """Best-effort insert — never raises (for hot paths like billing webhooks)."""
    try:
        with engine.begin() as conn:
            insert_ops_alert_event(
                conn,
                alert_type=alert_type,
                severity=severity,
                summary=summary,
                detail=detail,
                dedupe_key=dedupe_key,
            )
    except Exception:
        log.exception("ops_alert insert failed (alert_type=%s)", alert_type)
