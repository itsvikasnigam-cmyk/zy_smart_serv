"""M9 phase-2: auto-start SOP runs when a new ``ops_alert_events`` row is inserted."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

log = logging.getLogger("sop_alert_trigger")

SOP_TRIGGER_MAP_KEY = "alerts.sop_trigger_map"
SOP_AUTO_TRIGGER_KEY = "alerts.sop_auto_trigger_enabled"


def _load_json_config(conn: Connection, key: str) -> Any | None:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": key},
    ).fetchone()
    if not row:
        return None
    return row[0]


def _auto_trigger_enabled(conn: Connection) -> bool:
    raw = _load_json_config(conn, SOP_AUTO_TRIGGER_KEY)
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off")
    return bool(raw)


def _load_trigger_map(conn: Connection) -> dict[str, str]:
    raw = _load_json_config(conn, SOP_TRIGGER_MAP_KEY)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if v is None:
            continue
        slug = str(v).strip().lower()
        if slug:
            out[str(k)] = slug
    return out


def _client_id_from_detail(detail: dict[str, Any] | None) -> str | None:
    if not detail:
        return None
    cid = detail.get("client_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()
    return None


def maybe_trigger_sop_run_for_alert(
    conn: Connection,
    *,
    alert_type: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> str | None:
    """
    If ``alerts.sop_trigger_map`` maps ``alert_type`` → SOP slug, insert ``ops_run_logs``
    with ``trigger_type='alert'``. Returns new run id or None.
    """
    if not _auto_trigger_enabled(conn):
        return None

    slug = _load_trigger_map(conn).get(alert_type)
    if not slug:
        return None

    srow = conn.execute(
        text(
            """
            SELECT id::text, current_version
            FROM ops_sops
            WHERE slug = :slug AND status = 'active'
            LIMIT 1
            """
        ),
        {"slug": slug},
    ).fetchone()
    if not srow:
        log.warning(
            "sop auto-trigger: no active SOP for slug=%s (alert_type=%s)",
            slug,
            alert_type,
        )
        return None

    sop_id, ver = srow[0], int(srow[1])
    dk = (dedupe_key or "").strip() or None
    if dk:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM ops_run_logs
                WHERE sop_id = CAST(:sid AS uuid)
                  AND trigger_type = 'alert'
                  AND context_json->>'alert_dedupe_key' = :dk
                LIMIT 1
                """
            ),
            {"sid": sop_id, "dk": dk},
        ).fetchone()
        if exists:
            log.info(
                "sop auto-trigger skipped duplicate run sop=%s dedupe_key=%s",
                sop_id,
                dk,
            )
            return None

    client_id = _client_id_from_detail(detail)
    ctx: dict[str, Any] = {
        "alert_type": alert_type,
        "alert_summary": summary[:2000],
        "alert_detail": detail or {},
    }
    if dk:
        ctx["alert_dedupe_key"] = dk

    ins = conn.execute(
        text(
            """
            INSERT INTO ops_run_logs (
              sop_id, sop_version_at_run, context_json, trigger_type,
              created_by_user_id, client_id
            )
            VALUES (
              CAST(:sid AS uuid), :ver, CAST(:ctx AS jsonb), 'alert',
              NULL,
              CAST(:cid AS uuid)
            )
            RETURNING id::text
            """
        ),
        {
            "sid": sop_id,
            "ver": ver,
            "ctx": json.dumps(ctx, separators=(",", ":")),
            "cid": client_id,
        },
    ).fetchone()
    if not ins:
        return None
    run_id = ins[0]
    log.warning(
        "sop auto-trigger started run=%s sop=%s slug=%s alert_type=%s",
        run_id,
        sop_id,
        slug,
        alert_type,
    )
    return run_id
