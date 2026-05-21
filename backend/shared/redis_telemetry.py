"""Chat X: optional Redis stream buffer for telemetry traces (flush → Postgres)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.shared.config import Settings, settings
from backend.shared.pii_redaction import redact_pii_json
from backend.shared.redis_client import get_redis_client, redis_telemetry_buffer_enabled

log = logging.getLogger("redis_telemetry")

_MAXLEN_APPROX = 50_000


def buffer_trace_to_redis(
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
    cfg: Settings | None = None,
) -> bool:
    """Best-effort XADD; returns True when enqueued."""
    if not redis_telemetry_buffer_enabled(cfg):
        return False
    c = cfg or settings
    client = get_redis_client(c)
    if not client:
        return False
    payload = {
        "trace_id": trace_id[:64],
        "service": service[:64],
        "route": route[:256],
        "latency_ms": max(0, int(latency_ms)),
        "status": status[:32],
        "client_id": client_id or "",
        "chat_id": chat_id or "",
        "cost_inr": cost_inr,
        "meta": redact_pii_json(meta or {}),
    }
    try:
        client.xadd(
            c.redis_telemetry_stream_key,
            {"payload": json.dumps(payload, separators=(",", ":"))},
            maxlen=_MAXLEN_APPROX,
            approximate=True,
        )
        return True
    except Exception:
        log.debug("redis telemetry xadd failed", exc_info=True)
        return False


def flush_telemetry_stream_to_postgres(
    engine: Engine,
    *,
    max_entries: int = 500,
    cfg: Settings | None = None,
) -> int:
    """
    Read up to ``max_entries`` from the Redis stream and insert into ``telemetry_trace_logs``.
    Returns number of rows inserted.
    """
    c = cfg or settings
    if not redis_telemetry_buffer_enabled(c):
        return 0
    client = get_redis_client(c)
    if not client:
        return 0
    stream = c.redis_telemetry_stream_key
    try:
        entries = client.xrange(stream, count=max_entries)
    except Exception:
        log.exception("redis telemetry xrange failed")
        return 0
    if not entries:
        return 0

    inserted = 0
    entry_ids: list[str] = []
    with engine.begin() as conn:
        for entry_id, fields in entries:
            raw = fields.get("payload") if isinstance(fields, dict) else None
            if not raw:
                entry_ids.append(entry_id)
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                entry_ids.append(entry_id)
                continue
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
                    "tid": data.get("trace_id", "")[:64],
                    "cid": data.get("client_id") or "",
                    "chat": data.get("chat_id") or "",
                    "svc": (data.get("service") or "")[:64],
                    "route": (data.get("route") or "")[:256],
                    "lat": max(0, int(data.get("latency_ms") or 0)),
                    "cost": data.get("cost_inr"),
                    "st": (data.get("status") or "ok")[:32],
                    "meta": json.dumps(data.get("meta") or {}),
                },
            )
            inserted += 1
            entry_ids.append(entry_id)

    if entry_ids:
        try:
            client.xdel(stream, *entry_ids)
        except Exception:
            log.debug("redis telemetry xdel failed", exc_info=True)
    return inserted
