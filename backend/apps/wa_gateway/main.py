from __future__ import annotations

import hmac
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from backend.shared.config import settings
from backend.shared.db import engine, db_ping
from backend.workers.usage_metrics_common import (
    load_daily_inbound_limits_json,
    plan_soft_hard,
    should_mark_hard,
)
from .meta_payload import (
    extract_inbound_messages,
    inbound_matches_urgent_substrings,
    normalize_customer_phone_for_route,
    coerce_string_list_json,
)
from .status_payload import extract_meta_errors, extract_status_events


app = FastAPI(title="ZY Smart Serv - WA Gateway", version="0.1.0")

# Default when ops_runtime_config.m2.service_inactive_customer_reply is unset (SOP-aligned).
SERVICE_INACTIVE_CUSTOMER_DEFAULT = (
    "We're not able to continue this chat — your trial has ended or this workspace is inactive. "
    "Please complete billing or contact support to restore service."
)


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/ready", response_class=PlainTextResponse)
def ready() -> str:
    try:
        db_ping()
        return "ok"
    except Exception:
        raise HTTPException(status_code=503, detail="db not ready")


@app.get("/webhooks/meta", response_class=PlainTextResponse)
def meta_verify(request: Request) -> str:
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")
    if token != settings.meta_verify_token:
        raise HTTPException(status_code=403, detail="verify_token_mismatch")
    if mode != "subscribe":
        raise HTTPException(status_code=400, detail="invalid_mode")
    if not challenge:
        raise HTTPException(status_code=400, detail="missing_challenge")
    return challenge


def _validate_meta_signature(body: bytes, signature: str | None) -> None:
    if not settings.meta_app_secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="missing/invalid_signature")
    provided = signature.split("=", 1)[1].strip()
    mac = hmac.new(settings.meta_app_secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="signature_mismatch")


def _allow_zy_client_id_header() -> bool:
    """Explicit opt-in only (staging/prod stay closed even if APP_ENV=dev)."""
    return settings.wa_gateway_allow_client_id_header


def _coerce_jsonb_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            return int(s)
        except ValueError:
            return default
    return default


def _coerce_jsonb_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return default


def _merge_urgent_substrings(conn: Connection) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT key, value_json
            FROM ops_runtime_config
            WHERE key IN ('ai.urgent_bypass_substrings', 'routing.urgent_substrings')
            """
        )
    ).all()
    merged: list[str] = []
    for _, v in rows:
        merged.extend(coerce_string_list_json(v))
    seen: set[str] = set()
    out: list[str] = []
    for s in merged:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _load_service_inactive_reply(conn: Connection) -> str:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = 'm2.service_inactive_customer_reply'")
    ).fetchone()
    if not row or row[0] is None:
        return SERVICE_INACTIVE_CUSTOMER_DEFAULT
    raw = row[0]
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        t = raw.get("text") or raw.get("message")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return SERVICE_INACTIVE_CUSTOMER_DEFAULT


def _load_gateway_runtime(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(
        text(
            """
            SELECT key, value_json
            FROM ops_runtime_config
            WHERE key IN (
              'debounce.seconds','debounce.max_seconds',
              'debounce.adaptive.enabled','debounce.adaptive.two_msgs_within_sec'
            )
            """
        )
    ).all()
    cfg = {r[0]: r[1] for r in rows}
    return {
        "debounce_seconds": _coerce_jsonb_int(cfg.get("debounce.seconds"), 3),
        "max_debounce_seconds": _coerce_jsonb_int(cfg.get("debounce.max_seconds"), 10),
        "adaptive_enabled": _coerce_jsonb_bool(cfg.get("debounce.adaptive.enabled"), True),
        "adaptive_burst_sec": _coerce_jsonb_int(cfg.get("debounce.adaptive.two_msgs_within_sec"), 2),
    }


def _resolve_inbound_route(
    conn: Connection,
    *,
    to_phone_number_id: str | None,
    customer_phone_raw: str,
    x_zy_client_id: str | None,
) -> tuple[str, str | None]:
    if not to_phone_number_id:
        if _allow_zy_client_id_header() and x_zy_client_id:
            try:
                cid = str(uuid.UUID(x_zy_client_id.strip()))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_X-ZY-Client-Id") from exc
            return (cid, None)
        raise HTTPException(status_code=400, detail="unable_to_route_missing_phone_number_id")

    row = conn.execute(
        text(
            """
            SELECT id, client_id
            FROM wa_numbers
            WHERE meta_phone_number_id = :pid
            LIMIT 1
            """
        ),
        {"pid": to_phone_number_id},
    ).fetchone()

    phone_key = normalize_customer_phone_for_route(customer_phone_raw)

    if row:
        wa_number_id, mapped_client_id = row[0], row[1]
        if mapped_client_id is not None:
            return (str(mapped_client_id), str(wa_number_id))
        trial = conn.execute(
            text(
                """
                SELECT client_id
                FROM wa_trial_map
                WHERE wa_number_id = CAST(:wid AS uuid)
                  AND customer_phone_e164 = :phone_key
                LIMIT 1
                """
            ),
            {"wid": str(wa_number_id), "phone_key": phone_key},
        ).fetchone()
        if trial and trial[0]:
            return (str(trial[0]), str(wa_number_id))

    if _allow_zy_client_id_header() and x_zy_client_id:
        try:
            cid = str(uuid.UUID(x_zy_client_id.strip()))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_X-ZY-Client-Id") from exc
        return (cid, None)

    raise HTTPException(status_code=400, detail="unable_to_route_no_mapping")


def _fetch_client_row(conn: Connection, client_id: str) -> tuple[str, datetime | None] | None:
    row = conn.execute(
        text(
            """
            SELECT
              CASE
                WHEN bs.status IS NOT NULL AND lower(bs.status) IN (
                  'cancelled', 'canceled', 'completed', 'halted', 'payment_failed'
                ) THEN 'churned'
                ELSE c.entitlement_plan::text
              END AS effective_entitlement,
              c.trial_end
            FROM api_clients c
            LEFT JOIN LATERAL (
              SELECT status::text
              FROM bill_subscriptions s
              WHERE s.client_id = c.id
              ORDER BY s.updated_at DESC NULLS LAST
              LIMIT 1
            ) bs ON true
            WHERE c.id = CAST(:cid AS uuid)
            """
        ),
        {"cid": client_id},
    ).fetchone()
    if not row:
        return None
    ent, trial_end = row[0], row[1]
    return (str(ent), trial_end)


def _fetch_inbound_usage_today(conn: Connection, client_id: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(u.inbound_customer_messages, 0)
            FROM api_clients c
            LEFT JOIN bill_usage_daily u
              ON u.client_id = c.id
             AND u.usage_date = (timezone('utc', now()))::date
            WHERE c.id = CAST(:cid AS uuid)
            """
        ),
        {"cid": client_id},
    ).fetchone()
    if not row:
        return 0
    return int(row[0] or 0)


def _inbound_ai_block_reason(
    *,
    entitlement: str,
    trial_end: datetime | None,
    inbound_today_before_this_message: int,
    limits_root: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    Returns (reason_code, paywall_idem_suffix) if inbound should skip debounce batch (no AI enqueue path).
    Chat C batch_processor should still respect chat state; gateway blocks trial/usage before batch exists.
    """
    now_utc = datetime.now(timezone.utc)
    day = now_utc.date().isoformat()
    if entitlement == "churned":
        return ("churned", f"day:{day}")
    if entitlement == "trial" and trial_end is not None:
        te = trial_end
        if te.tzinfo is None:
            te = te.replace(tzinfo=timezone.utc)
        if te < now_utc:
            return ("trial_expired", f"day:{day}")
    _, hard = plan_soft_hard(limits_root, entitlement)
    projected = inbound_today_before_this_message + 1
    if should_mark_hard(projected, hard):
        return ("usage_hard", f"usage:{day}")
    return (None, None)


def _enqueue_paywall_outbox(
    conn: Connection,
    *,
    client_id: str,
    chat_id: str,
    to_phone: str,
    from_wa_number_id: str | None,
    idempotency_key: str,
    body: str,
) -> None:
    if not from_wa_number_id:
        return
    conn.execute(
        text(
            """
            INSERT INTO wa_outbox(
              client_id, chat_id, to_phone_e164, from_wa_number_id,
              kind, body_text, reply_to_batch_id, idempotency_key, status
            )
            VALUES (
              CAST(:client_id AS uuid), CAST(:chat_id AS uuid), :to_phone, CAST(:from_id AS uuid),
              'PAYWALL', :body, NULL, :idem, 'PENDING'
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """
        ),
        {
            "client_id": client_id,
            "chat_id": chat_id,
            "to_phone": to_phone,
            "from_id": from_wa_number_id,
            "body": body,
            "idem": idempotency_key,
        },
    )


def _open_or_extend_batch(
    conn: Connection,
    *,
    chat_id: str,
    debounce_seconds: int,
    max_debounce_seconds: int,
    adaptive_enabled: bool,
    burst_sec: int,
    urgent: bool,
) -> None:
    conn.execute(
        text(
            """
            WITH existing AS (
              SELECT id, max_process_after, last_inbound_msg_at
              FROM inbox_inbound_batches
              WHERE chat_id = CAST(:chat_id AS uuid) AND status = 'OPEN'
              ORDER BY opened_at DESC
              LIMIT 1
            ),
            ins AS (
              INSERT INTO inbox_inbound_batches(
                chat_id, status, opened_at, process_after, max_process_after, last_inbound_msg_at, inbound_msg_count
              )
              SELECT
                CAST(:chat_id AS uuid),
                'OPEN',
                now(),
                CASE
                  WHEN :urgent THEN now()
                  ELSE now() + (
                    CASE
                      WHEN :adaptive_enabled AND EXISTS (
                        SELECT 1 FROM existing e
                        WHERE e.last_inbound_msg_at IS NOT NULL
                          AND (now() - e.last_inbound_msg_at)
                              < make_interval(secs => :burst_sec)
                      )
                      THEN (:max_debounce || ' seconds')::interval
                      ELSE (:debounce || ' seconds')::interval
                    END
                  )
                END,
                now() + (:max_debounce || ' seconds')::interval,
                now(),
                1
              WHERE NOT EXISTS (SELECT 1 FROM existing)
              RETURNING id
            )
            UPDATE inbox_inbound_batches b
            SET
              last_inbound_msg_at = now(),
              inbound_msg_count = inbound_msg_count + 1,
              process_after = CASE
                WHEN :urgent THEN now()
                WHEN :adaptive_enabled
                     AND b.last_inbound_msg_at IS NOT NULL
                     AND (now() - b.last_inbound_msg_at)
                         < make_interval(secs => :burst_sec)
                  THEN LEAST(now() + (:max_debounce || ' seconds')::interval, b.max_process_after)
                ELSE LEAST(now() + (:debounce || ' seconds')::interval, b.max_process_after)
              END
            WHERE b.id = (SELECT id FROM existing)
            """
        ),
        {
            "chat_id": str(chat_id),
            "debounce": debounce_seconds,
            "max_debounce": max_debounce_seconds,
            "adaptive_enabled": adaptive_enabled,
            "burst_sec": burst_sec,
            "urgent": urgent,
        },
    )


@app.post("/webhooks/meta/inbound")
async def meta_inbound(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_zy_client_id: str | None = Header(default=None, alias="X-ZY-Client-Id"),
) -> dict[str, Any]:
    """
    Store-first ingestion. **Does not call the AI engine** — only DB writes + optional PAYWALL outbox;
    ``batch_processor`` (Chat C) seals batches and invokes the AI engine respond HTTP API (M1 contract in HANDOFF) — never from this webhook path.

    Routing: ``wa_numbers`` / ``wa_trial_map``. Optional ``X-ZY-Client-Id`` only when
    ``WA_GATEWAY_ALLOW_CLIENT_ID_HEADER=true`` (see Settings).
    """
    body = await request.body()
    _validate_meta_signature(body, x_hub_signature_256)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")

    messages = extract_inbound_messages(payload)
    if not messages:
        return {"ok": True}

    extra_inbound_this_tx: dict[str, int] = {}

    try:
        with engine.begin() as conn:
            rt = _load_gateway_runtime(conn)
            limits_root = load_daily_inbound_limits_json(conn)
            urgent_substrings = _merge_urgent_substrings(conn)
            paywall_body = _load_service_inactive_reply(conn)

            for m in messages:
                routed_client_id, routed_wa_number_id = _resolve_inbound_route(
                    conn,
                    to_phone_number_id=m.to_phone_number_id,
                    customer_phone_raw=m.from_phone,
                    x_zy_client_id=x_zy_client_id,
                )
                client_id = routed_client_id

                crow = _fetch_client_row(conn, client_id)
                if not crow:
                    raise HTTPException(status_code=400, detail="unknown_client")
                entitlement, trial_end = crow

                base_usage = _fetch_inbound_usage_today(conn, client_id)
                inbound_before = base_usage + extra_inbound_this_tx[client_id]

                block_reason, idem_suffix = _inbound_ai_block_reason(
                    entitlement=entitlement,
                    trial_end=trial_end,
                    inbound_today_before_this_message=inbound_before,
                    limits_root=limits_root,
                )

                customer_phone = normalize_customer_phone_for_route(m.from_phone)

                chat_id = conn.execute(
                    text(
                        """
                        INSERT INTO inbox_chats (client_id, customer_phone, waba_number, state, last_customer_msg_at)
                        VALUES (CAST(:client_id AS uuid), :customer_phone, CAST(:waba_number AS uuid), 'AI_ACTIVE', now())
                        ON CONFLICT (client_id, customer_phone)
                        DO UPDATE SET last_customer_msg_at = EXCLUDED.last_customer_msg_at,
                                      waba_number = COALESCE(inbox_chats.waba_number, EXCLUDED.waba_number)
                        RETURNING id
                        """
                    ),
                    {
                        "client_id": client_id,
                        "customer_phone": customer_phone,
                        "waba_number": routed_wa_number_id,
                    },
                ).scalar_one()

                ins_row = conn.execute(
                    text(
                        """
                        INSERT INTO inbox_messages (chat_id, direction, sender, text, timestamp, meta_msg_id, meta_payload)
                        VALUES (CAST(:chat_id AS uuid), 'in', 'customer', :text, now(), :meta_msg_id, CAST(:meta_payload AS jsonb))
                        ON CONFLICT (meta_msg_id) WHERE meta_msg_id IS NOT NULL DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "chat_id": str(chat_id),
                        "text": m.text,
                        "meta_msg_id": m.meta_msg_id,
                        "meta_payload": json.dumps(m.raw),
                    },
                ).fetchone()
                if ins_row is None:
                    continue

                extra_inbound_this_tx[client_id] = extra_inbound_this_tx.get(client_id, 0) + 1

                if block_reason:
                    idem = f"paywall:{block_reason}:{client_id}:{idem_suffix or 'na'}"
                    _enqueue_paywall_outbox(
                        conn,
                        client_id=client_id,
                        chat_id=str(chat_id),
                        to_phone=customer_phone,
                        from_wa_number_id=routed_wa_number_id,
                        idempotency_key=idem[:512],
                        body=paywall_body,
                    )
                    continue

                urgent = inbound_matches_urgent_substrings(m.text, urgent_substrings)
                _open_or_extend_batch(
                    conn,
                    chat_id=str(chat_id),
                    debounce_seconds=rt["debounce_seconds"],
                    max_debounce_seconds=rt["max_debounce_seconds"],
                    adaptive_enabled=rt["adaptive_enabled"],
                    burst_sec=rt["adaptive_burst_sec"],
                    urgent=urgent,
                )

        return {"ok": True, "stored": len(messages)}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        detail = str(getattr(exc, "orig", exc) or exc)
        if settings.app_env == "dev":
            raise HTTPException(status_code=500, detail=f"database_error:{detail}") from exc
        raise HTTPException(status_code=500, detail="database_error") from exc


@app.post("/webhooks/meta/status")
async def meta_status(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    body = await request.body()
    _validate_meta_signature(body, x_hub_signature_256)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")

    events = extract_status_events(payload)
    if not events:
        return {"ok": True}

    with engine.begin() as conn:
        for ev in events:
            row = conn.execute(
                text("SELECT client_id FROM wa_outbox WHERE meta_message_id = :mid LIMIT 1"),
                {"mid": ev.meta_message_id},
            ).fetchone()
            if not row:
                continue
            client_id = str(row[0])

            conn.execute(
                text(
                    """
                    INSERT INTO wa_status_events (client_id, meta_message_id, event_type, event_at, raw_json)
                    VALUES (CAST(:cid AS uuid), :mid, :etype, now(), CAST(:raw AS jsonb))
                    """
                ),
                {"cid": client_id, "mid": ev.meta_message_id, "etype": ev.event_type, "raw": json.dumps(ev.raw)},
            )

            conn.execute(
                text(
                    """
                    UPDATE wa_outbox
                    SET status = CASE
                      WHEN :etype = 'DELIVERED' THEN 'DELIVERED'
                      WHEN :etype = 'READ' THEN 'READ'
                      WHEN :etype = 'FAILED' THEN 'FAILED'
                      ELSE status
                    END
                    WHERE meta_message_id = :mid
                    """
                ),
                {"etype": ev.event_type, "mid": ev.meta_message_id},
            )

    return {"ok": True, "updated": len(events)}


@app.post("/webhooks/meta/errors")
async def meta_errors(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    """Optional Meta system / message error webhook sink (append-only JSON)."""
    body = await request.body()
    _validate_meta_signature(body, x_hub_signature_256)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")

    errs = extract_meta_errors(payload)
    if not errs:
        return {"ok": True, "stored": 0}

    with engine.begin() as conn:
        for raw in errs:
            conn.execute(
                text(
                    """
                    INSERT INTO wa_meta_webhook_errors (raw_json)
                    VALUES (CAST(:raw AS jsonb))
                    """
                ),
                {"raw": json.dumps(raw)},
            )

    return {"ok": True, "stored": len(errs)}
