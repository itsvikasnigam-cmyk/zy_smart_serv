from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

SOP_TRIGGER_MAP_KEY = "alerts.sop_trigger_map"

_TRIGGER_BY_ALERT: dict[str, str] = {
    "OUTBOX_DEAD_SPIKE": "alert:outbox_dead_spike",
    "META_WEBHOOK_ERROR_SPIKE": "alert:meta_webhook_error_spike",
}


def _load_sop_trigger_map(conn: Connection) -> dict[str, str]:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": SOP_TRIGGER_MAP_KEY},
    ).fetchone()
    if not row or not isinstance(row[0], dict):
        return {}
    out: dict[str, str] = {}
    for k, v in row[0].items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def maybe_create_auto_sop_run(
    conn: Connection,
    *,
    alert_type: str,
    ops_alert_event_id: str | None,
    detail: dict[str, Any] | None,
) -> str | None:
    """
    When ``alerts.sop_trigger_map`` maps ``alert_type`` → SOP slug, insert an ``ops_run_logs`` row.

    Returns run id when created, else None. Idempotent per alert event when ``ops_alert_event_id`` set.
    """
    slug_map = _load_sop_trigger_map(conn)
    slug = slug_map.get(alert_type)
    if not slug:
        return None

    sop = conn.execute(
        text(
            """
            SELECT id::text, current_version FROM ops_sops
            WHERE slug = :slug AND status = 'active'
            LIMIT 1
            """
        ),
        {"slug": slug.lower()},
    ).fetchone()
    if not sop:
        logger.warning("auto SOP run skipped: slug %s not found", slug)
        return None

    sop_id, ver = sop[0], int(sop[1])
    trigger_type = _TRIGGER_BY_ALERT.get(alert_type, "auto")
    ctx: dict[str, Any] = {
        "alert_type": alert_type,
        "source": "alert_eval_worker",
        "detail": detail or {},
    }
    if ops_alert_event_id:
        ctx["ops_alert_event_id"] = ops_alert_event_id
        existing = conn.execute(
            text(
                """
                SELECT id::text FROM ops_run_logs
                WHERE trigger_type = :trig
                  AND context_json->>'ops_alert_event_id' = :eid
                LIMIT 1
                """
            ),
            {"trig": trigger_type, "eid": ops_alert_event_id},
        ).fetchone()
        if existing:
            return None

    ins = conn.execute(
        text(
            """
            INSERT INTO ops_run_logs (
              sop_id, sop_version_at_run, context_json, trigger_type, created_by_user_id, client_id
            )
            VALUES (
              CAST(:sid AS uuid), :ver, CAST(:ctx AS jsonb), :trig, NULL, NULL
            )
            RETURNING id::text
            """
        ),
        {
            "sid": sop_id,
            "ver": ver,
            "ctx": json.dumps(ctx),
            "trig": trigger_type,
        },
    ).fetchone()
    if not ins:
        return None
    run_id = ins[0]
    logger.info("auto SOP run created run_id=%s sop_slug=%s alert=%s", run_id, slug, alert_type)
    return run_id
