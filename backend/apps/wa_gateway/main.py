from __future__ import annotations

import hmac
import hashlib
import json
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.config import settings
from backend.shared.db import engine, db_ping
from .meta_payload import extract_inbound_messages, normalize_customer_phone_for_route
from .status_payload import extract_status_events


app = FastAPI(title="ZY Smart Serv - WA Gateway", version="0.1.0")


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
        raise HTTPException(status_code=403, detail="verify token mismatch")
    if mode != "subscribe":
        raise HTTPException(status_code=400, detail="invalid mode")
    if not challenge:
        raise HTTPException(status_code=400, detail="missing challenge")
    return challenge


def _validate_meta_signature(body: bytes, signature: str | None) -> None:
    if not settings.meta_app_secret:
        # Dev-friendly: allow no signature when secret isn't configured.
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="missing/invalid signature")
    provided = signature.split("=", 1)[1].strip()
    mac = hmac.new(settings.meta_app_secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="signature mismatch")


def _allow_zy_client_id_header() -> bool:
    """Narrow dev escape hatch: never in prod."""
    return settings.app_env == "dev"


def _resolve_inbound_route(
    conn: Connection,
    *,
    to_phone_number_id: str | None,
    customer_phone_raw: str,
    x_zy_client_id: str | None,
) -> tuple[str, str | None]:
    """
    Resolve (client_id, wa_number_id) for an inbound message.

    Order:
    1) wa_numbers.meta_phone_number_id with non-null client_id (prod / dedicated BYON)
    2) wa_numbers row for shared line (client_id null) + wa_trial_map by wa_number_id + customer phone
    3) optional X-ZY-Client-Id when app_env=dev (no wa_number_id)
    """
    if not to_phone_number_id:
        if _allow_zy_client_id_header() and x_zy_client_id:
            try:
                cid = str(uuid.UUID(x_zy_client_id.strip()))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid X-ZY-Client-Id (expected UUID)") from exc
            return (cid, None)
        raise HTTPException(status_code=400, detail="unable to route (missing phone_number_id)")

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
            raise HTTPException(status_code=400, detail="invalid X-ZY-Client-Id (expected UUID)") from exc
        return (cid, None)

    raise HTTPException(status_code=400, detail="unable to route (no phone_number_id mapping)")


@app.post("/webhooks/meta/inbound")
async def meta_inbound(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_zy_client_id: str | None = Header(default=None, alias="X-ZY-Client-Id"),
) -> dict[str, Any]:
    """
    Store-first ingestion.

    Routing: wa_numbers (prod/BYON) or wa_trial_map (shared trial line). In dev only,
    X-ZY-Client-Id may still force client_id when DB mapping is absent.
    """
    body = await request.body()
    _validate_meta_signature(body, x_hub_signature_256)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    messages = extract_inbound_messages(payload)
    if not messages:
        return {"ok": True}

    # Store-first: insert messages (dedupe on meta_msg_id) and create chat if missing.
    # We only return 200 after commit.
    #
    # Debounce batching:
    # - default: 3s; max: 10s (from ops_runtime_config)
    # - batch is per chat; single OPEN batch is extended until due, then worker seals it.
    with engine.begin() as conn:
        cfg_rows = conn.execute(
            text(
                """
                SELECT key, value_json
                FROM ops_runtime_config
                WHERE key IN ('debounce.seconds','debounce.max_seconds')
                """
            )
        ).all()
        cfg = {r[0]: r[1] for r in cfg_rows}
        debounce_seconds = int(cfg.get("debounce.seconds", 3))
        max_debounce_seconds = int(cfg.get("debounce.max_seconds", 10))

        for m in messages:
            routed_client_id, routed_wa_number_id = _resolve_inbound_route(
                conn,
                to_phone_number_id=m.to_phone_number_id,
                customer_phone_raw=m.from_phone,
                x_zy_client_id=x_zy_client_id,
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
                {"client_id": routed_client_id, "customer_phone": customer_phone, "waba_number": routed_wa_number_id},
            ).scalar_one()

            conn.execute(
                text(
                    """
                    INSERT INTO inbox_messages (chat_id, direction, sender, text, timestamp, meta_msg_id, meta_payload)
                    VALUES (CAST(:chat_id AS uuid), 'in', 'customer', :text, now(), :meta_msg_id, CAST(:meta_payload AS jsonb))
                    ON CONFLICT (meta_msg_id) DO NOTHING
                    """
                ),
                {
                    "chat_id": str(chat_id),
                    "text": m.text,
                    "meta_msg_id": m.meta_msg_id,
                    "meta_payload": json.dumps(m.raw),
                },
            )

            # Create or extend an OPEN batch for this chat.
            # Rules:
            # - if no OPEN batch exists: opened_at=now, process_after=now+debounce, max_process_after=now+max
            # - if OPEN exists: bump inbound_msg_count, last_inbound_msg_at, and process_after=min(now+debounce, max_process_after)
            conn.execute(
                text(
                    """
                    WITH existing AS (
                      SELECT id, max_process_after
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
                        now() + (:debounce || ' seconds')::interval,
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
                      process_after = LEAST(
                        now() + (:debounce || ' seconds')::interval,
                        b.max_process_after
                      )
                    WHERE b.id = (SELECT id FROM existing)
                    """
                ),
                {
                    "chat_id": str(chat_id),
                    "debounce": debounce_seconds,
                    "max_debounce": max_debounce_seconds,
                },
            )

    return {"ok": True, "stored": len(messages)}


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
        raise HTTPException(status_code=400, detail="invalid json")

    events = extract_status_events(payload)
    if not events:
        return {"ok": True}

    with engine.begin() as conn:
        for ev in events:
            # Update outbox status best-effort; client_id is derived from outbox row.
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

