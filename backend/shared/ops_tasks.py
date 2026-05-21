"""Chat W: incident tasks from critical ops alerts (alongside SOP auto-runs)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("ops_tasks")

OPS_TASK_POLICY_KEY = "alerts.ops_task_policy"

_DEFAULT_POLICY = {
    "enabled": True,
    "min_severity": "warning",
    "alert_types": [
        "OUTBOX_DEAD_SPIKE",
        "META_WEBHOOK_ERROR_SPIKE",
        "BILLING_WEBHOOK_PROCESSING_ERROR",
        "INBOX_AGENT_SLA_BREACH",
        "OWNER_WAIT_8H",
    ],
}

_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}
_PRIORITY_FROM_SEVERITY = {"error": "critical", "warning": "high", "info": "normal"}


def merge_ops_task_policy(value_json: Any | None) -> dict[str, Any]:
    out = dict(_DEFAULT_POLICY)
    if isinstance(value_json, dict):
        for key, val in value_json.items():
            if key in out and val is not None:
                out[key] = val
    return out


def load_ops_task_policy_conn(conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
        {"k": OPS_TASK_POLICY_KEY},
    ).fetchone()
    return merge_ops_task_policy(row[0] if row else None)


def _severity_meets_min(severity: str, min_severity: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(min_severity, 1)


def _latest_sop_run_id_for_alert(conn: Connection, dedupe_key: str | None) -> str | None:
    if not dedupe_key:
        return None
    row = conn.execute(
        text(
            """
            SELECT id::text
            FROM ops_run_logs
            WHERE context_json->>'alert_dedupe_key' = :dk
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"dk": dedupe_key},
    ).fetchone()
    return str(row[0]) if row else None


def _task_title(alert_type: str, summary: str) -> str:
    short = (summary or "").strip()
    if len(short) > 120:
        short = short[:117] + "..."
    return f"[{alert_type}] {short}" if short else f"[{alert_type}] incident"


def maybe_create_ops_task_for_alert(
    conn: Connection,
    *,
    alert_type: str,
    severity: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """
    Create one open ``ops_tasks`` row when policy allows (idempotent on ``alert_dedupe_key``).
    Returns True when a new task was inserted.
    """
    policy = load_ops_task_policy_conn(conn)
    if not policy.get("enabled", True):
        return False
    allowed = policy.get("alert_types") or []
    if alert_type not in allowed:
        return False
    min_sev = str(policy.get("min_severity") or "warning")
    if not _severity_meets_min(severity, min_sev):
        return False

    dk = (dedupe_key or "").strip() or None
    priority = _PRIORITY_FROM_SEVERITY.get(severity, "normal")
    detail_obj = dict(detail or {})
    client_id = detail_obj.get("client_id")
    if client_id is not None:
        client_id = str(client_id).strip() or None

    sop_run_id = _latest_sop_run_id_for_alert(conn, dk)
    title = _task_title(alert_type, summary)

    try:
        row = conn.execute(
            text(
                """
                INSERT INTO ops_tasks (
                  title, status, priority, alert_type, alert_dedupe_key,
                  summary, detail_json, client_id, sop_run_id
                )
                VALUES (
                  :title, 'open', :priority, :atype, :dk,
                  :summary, CAST(:detail AS jsonb),
                  CASE WHEN :cid = '' THEN NULL ELSE CAST(:cid AS uuid) END,
                  CASE WHEN :rid = '' THEN NULL ELSE CAST(:rid AS uuid) END
                )
                RETURNING id::text
                """
            ),
            {
                "title": title[:500],
                "priority": priority,
                "atype": alert_type,
                "dk": dk,
                "summary": summary[:4000],
                "detail": json.dumps(detail_obj, separators=(",", ":")),
                "cid": client_id or "",
                "rid": sop_run_id or "",
            },
        ).fetchone()
    except IntegrityError:
        return False
    if not row:
        return False
    task_id = str(row[0])
    conn.execute(
        text(
            """
            INSERT INTO ops_task_events (task_id, action, actor_user_id, note)
            VALUES (CAST(:tid AS uuid), 'created', NULL, :note)
            """
        ),
        {
            "tid": task_id,
            "note": f"Auto-created from alert {alert_type}",
        },
    )
    log.warning("ops_task created id=%s alert_type=%s", task_id, alert_type)
    return True


def resolve_ops_task(
    conn: Connection,
    *,
    task_id: str,
    resolved_by_user_id: str | None = None,
    resolution_note: str | None = None,
) -> bool:
    uid = (resolved_by_user_id or "").strip()
    row = conn.execute(
        text(
            """
            UPDATE ops_tasks
            SET status = 'resolved',
                resolved_at = now(),
                updated_at = now(),
                resolved_by_user_id = CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END,
                resolution_note = :note
            WHERE id = CAST(:tid AS uuid) AND status = 'open'
            RETURNING id::text
            """
        ),
        {
            "tid": task_id,
            "uid": uid,
            "note": (resolution_note or "").strip() or None,
        },
    ).fetchone()
    if not row:
        return False
    conn.execute(
        text(
            """
            INSERT INTO ops_task_events (task_id, action, actor_user_id, note)
            VALUES (
              CAST(:tid AS uuid), 'resolved',
              CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END,
              :note
            )
            """
        ),
        {
            "tid": task_id,
            "uid": uid,
            "note": (resolution_note or "").strip() or "resolved",
        },
    )
    return True
