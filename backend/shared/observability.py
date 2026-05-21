"""Option C phase 5: best-effort telemetry traces + AI misfire log (never raises on hot path)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from backend.shared.pii_redaction import redact_pii_json, redact_pii_text

log = logging.getLogger("observability")


def new_trace_id() -> str:
    return str(uuid.uuid4())


def record_trace(
    conn: Connection,
    *,
    trace_id: str,
    service: str,
    route: str,
    latency_ms: int,
    status: str = "ok",
    client_id: str | None = None,
    chat_id: str | None = None,
    cost_inr: float | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO telemetry_trace_logs (
              trace_id, client_id, chat_id, service, route, latency_ms, cost_inr, status, meta
            )
            VALUES (
              :tid,
              CASE WHEN :cid = '' THEN NULL ELSE CAST(:cid AS uuid) END,
              CASE WHEN :chat = '' THEN NULL ELSE CAST(:chat AS uuid) END,
              :svc,
              :route,
              :lat,
              :cost,
              :st,
              CAST(:meta AS jsonb)
            )
            """
        ),
        {
            "tid": trace_id[:64],
            "cid": client_id or "",
            "chat": chat_id or "",
            "svc": service[:64],
            "route": route[:256],
            "lat": max(0, int(latency_ms)),
            "cost": cost_inr,
            "st": status[:32],
            "meta": json.dumps(redact_pii_json(meta or {})),
        },
    )


def record_misfire(
    conn: Connection,
    *,
    source: str,
    reason: str,
    trace_id: str | None = None,
    client_id: str | None = None,
    chat_id: str | None = None,
    batch_text_preview: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    preview = (redact_pii_text(batch_text_preview) or "")[:500]
    conn.execute(
        text(
            """
            INSERT INTO misfires_log (
              trace_id, client_id, chat_id, source, reason, batch_text_preview, detail
            )
            VALUES (
              :tid,
              CASE WHEN :cid = '' THEN NULL ELSE CAST(:cid AS uuid) END,
              CASE WHEN :chat = '' THEN NULL ELSE CAST(:chat AS uuid) END,
              :src,
              :reason,
              :preview,
              CAST(:detail AS jsonb)
            )
            """
        ),
        {
            "tid": (trace_id or "")[:64] or None,
            "cid": client_id or "",
            "chat": chat_id or "",
            "src": source[:64],
            "reason": reason[:128],
            "preview": preview or None,
            "detail": json.dumps(redact_pii_json(detail or {})),
        },
    )


def record_trace_safe(
    engine: Engine,
    **kwargs: Any,
) -> None:
    try:
        from backend.shared.redis_telemetry import buffer_trace_to_redis

        buffer_trace_to_redis(
            trace_id=kwargs.get("trace_id", ""),
            service=kwargs.get("service", ""),
            route=kwargs.get("route", ""),
            latency_ms=int(kwargs.get("latency_ms") or 0),
            status=kwargs.get("status", "ok"),
            client_id=kwargs.get("client_id"),
            chat_id=kwargs.get("chat_id"),
            cost_inr=kwargs.get("cost_inr"),
            meta=kwargs.get("meta"),
        )
    except Exception:
        log.debug("redis telemetry buffer skipped", exc_info=True)
    try:
        with engine.begin() as conn:
            record_trace(conn, **kwargs)
    except Exception:
        log.exception("record_trace failed")


def record_misfire_safe(engine: Engine, **kwargs: Any) -> None:
    try:
        with engine.begin() as conn:
            record_misfire(conn, **kwargs)
    except Exception:
        log.exception("record_misfire failed")
