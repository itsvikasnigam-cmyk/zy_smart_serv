from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.apps.ai_engine.helpers.respond_logic import NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
from backend.shared.config import settings as _settings
from backend.shared.customer_blocks import lookup_customer_block
from backend.shared.db import engine
from backend.shared.inbox_notify import notify_handoff_states
from backend.shared.inbox_typing_lock import has_active_agent_typing, is_typing_lock_enabled
from backend.shared.observability import new_trace_id, record_misfire_safe, record_trace_safe
from backend.shared.product_config import load_paywall_reply
from backend.workers.usage_metrics_common import (
    load_daily_inbound_limits_json,
    plan_soft_hard,
    should_mark_hard,
)


@dataclass(frozen=True)
class DebounceConfig:
    debounce_seconds: int = 3
    max_debounce_seconds: int = 10


INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()
AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://127.0.0.1:8083")

PG_NOTIFY_CHANNEL = "zy_chat_events"

# Align with wa_gateway `SERVICE_INACTIVE_CUSTOMER_DEFAULT` for second-line PAYWALL body.
SERVICE_INACTIVE_CUSTOMER_DEFAULT = (
    "We're not able to continue this chat — your trial has ended or this workspace is inactive. "
    "Please complete billing or contact support to restore service."
)

NEEDS_OWNER_REPLY_OPS_KEY = "ai.needs_owner_data_customer_reply"


def apply_u2_strict_after_ai(ai: dict[str, Any]) -> dict[str, Any]:
    """
    Blueprint **U2** (batch path): urgent classification must not send a generic **REPLY**
    to the customer. Normalize engine **REPLY** + urgent routing into **HANDOFF** so the
    worker sets **HUMAN_REQ** + owner alerts (same branch as explicit handoff).
    """
    if not isinstance(ai, dict):
        return ai
    action = str(ai.get("action") or "REPLY")
    if action != "REPLY":
        return ai
    routing = str(ai.get("routing_intent") or "")
    intent = str(ai.get("intent") or "")
    if routing == "urgent" or intent == "urgent":
        out = dict(ai)
        out["action"] = "HANDOFF"
        out["handoff_reason"] = "urgent_time_sensitive_u2"
        out["reply_text"] = None
        return out
    return ai


def second_line_paywall_block(
    *,
    entitlement: str,
    trial_end: datetime | None,
    inbound_today: int,
    limits_root: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    Second-line gate before ``httpx`` → ``/ai/respond`` for **legacy OPEN** batches sealed
    after a paywall / entitlement transition (**HANDOFF** Known gaps §1). Uses the same
    entitlement + usage-hard rules as ``wa_gateway._inbound_ai_block_reason``, but
    evaluates against **current** ``bill_usage_daily`` counts (messages already stored).
    """
    now_utc = datetime.now(tz=timezone.utc)
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
    if should_mark_hard(inbound_today, hard):
        return ("usage_hard", f"usage:{day}")
    return (None, None)


def _fetch_client_row(conn: Connection, client_id: str) -> tuple[str, datetime | None] | None:
    """DB-only entitlement snapshot (mirrors ``wa_gateway.main._fetch_client_row``)."""
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
    return (str(row[0]), row[1])


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


def _load_needs_owner_customer_reply_text(conn: Connection) -> str:
    """Same product copy resolution as ``ai_engine`` + ``NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED``."""
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": NEEDS_OWNER_REPLY_OPS_KEY},
    ).fetchone()
    fixed = NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    if not row or row[0] is None:
        return fixed
    raw = row[0]
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        t = raw.get("text") or raw.get("message")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return fixed


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


def _emit_chat_event_notify(conn, *, client_id: str, event: str, data: dict) -> None:
    """Fire-and-forget NOTIFY for client_api (or dev tools) listening on PG_NOTIFY_CHANNEL."""
    payload = json.dumps({"client_id": client_id, "event": event, "data": data}, separators=(",", ":"))
    if len(payload) > 7500:
        payload = json.dumps(
            {"client_id": client_id, "event": event, "data": {"chat_id": data.get("chat_id"), "state": data.get("state")}},
            separators=(",", ":"),
        )
    conn.execute(text("SELECT pg_notify(:channel, CAST(:payload AS text))"), {"channel": PG_NOTIFY_CHANNEL, "payload": payload})


def _get_debounce_config() -> DebounceConfig:
    # Read runtime config; fall back to defaults.
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT key, value_json
                FROM ops_runtime_config
                WHERE key IN ('debounce.seconds','debounce.max_seconds')
                """
            )
        ).all()
    values = {r[0]: r[1] for r in rows}
    return DebounceConfig(
        debounce_seconds=int(values.get("debounce.seconds", 3)),
        max_debounce_seconds=int(values.get("debounce.max_seconds", 10)),
    )


def _acquire_lock(conn, lock_key: str, ttl_seconds: int = 120) -> bool:
    # Upsert lock only if expired or owned by self.
    res = conn.execute(
        text(
            """
            INSERT INTO processing_locks(lock_key, owner_id, acquired_at, expires_at)
            VALUES (:k, :o, now(), now() + (:ttl || ' seconds')::interval)
            ON CONFLICT (lock_key)
            DO UPDATE SET owner_id = EXCLUDED.owner_id,
                          acquired_at = EXCLUDED.acquired_at,
                          expires_at = EXCLUDED.expires_at
            WHERE processing_locks.expires_at < now()
               OR processing_locks.owner_id = :o
            RETURNING lock_key
            """
        ),
        {"k": lock_key, "o": INSTANCE_ID, "ttl": ttl_seconds},
    ).fetchone()
    return bool(res)


def _open_or_extend_batch(conn, chat_id: str, cfg: DebounceConfig) -> None:
    # Not used yet; creation happens in webhook in Phase C.
    _ = chat_id
    _ = cfg


def run_once() -> int:
    """
    Process due batches:
    - seal batch
    - build batch_text from inbound messages since opened_at
    - optional **second-line paywall** before ``httpx`` → ``/ai/respond`` (legacy OPEN after
      entitlement / usage transition — aligns with **HANDOFF** Known gaps §1 + **Chat B** gateway)
    - call AI engine
    - **U2 strict:** normalize urgent **REPLY** (``intent`` / ``routing_intent`` ``urgent``) to
      **HANDOFF** so the customer does not receive a generic AI line; inbox → **HUMAN_REQ** + owner alerts
    - enqueue a single outbox message (idempotent) when action is REPLY
    - on HANDOFF: set inbox_chats to HUMAN_REQ + pg_notify; on NEEDS_OWNER_DATA: WAITING_OWNER_DATA
      + customer ``wa_outbox`` **AI_REPLY** using the same copy as ``ai_engine`` (ops key + fixed default)
    - mark batch PROCESSED

    NOTE (M3/M4 client_api): this worker is in a separate process. WS fan-out
    is the client_api DBPoller's responsibility — it picks up the new wa_outbox
    row (kind='AI_REPLY') and pushes ``message_new`` to subscribed agents. Do
    not import client_api from this worker. If you need lower-latency fan-out
    later, rely on ``pg_notify('zy_chat_events', …)`` (see ``dev_listen_chat_events.py``)
    and/or have client_api subscribe with ``LISTEN zy_chat_events``.
    """
    cfg = _get_debounce_config()
    processed = 0

    with engine.begin() as conn:
        batches = conn.execute(
            text(
                """
                SELECT id, chat_id, opened_at
                FROM inbox_inbound_batches
                WHERE status = 'OPEN' AND process_after <= now()
                ORDER BY process_after ASC
                LIMIT 25
                """
            )
        ).all()

        for batch_id, chat_id, opened_at in batches:
            if not _acquire_lock(conn, f"batch:{batch_id}", ttl_seconds=120):
                continue
            if not _acquire_lock(conn, f"chat:{chat_id}", ttl_seconds=120):
                continue

            sealed = conn.execute(
                text(
                    """
                    UPDATE inbox_inbound_batches
                    SET status='SEALED', sealed_at=now()
                    WHERE id=CAST(:id AS uuid) AND status='OPEN'
                    RETURNING sealed_at
                    """
                ),
                {"id": str(batch_id)},
            ).fetchone()
            if not sealed or sealed[0] is None:
                continue
            sealed_at = sealed[0]
            # Load chat context
            chat_row = conn.execute(
                text(
                    """
                    SELECT c.id, c.client_id, c.customer_phone, c.waba_number, c.state, c.ai_paused_until
                    FROM inbox_chats c
                    WHERE c.id = CAST(:chat_id AS uuid)
                    """
                ),
                {"chat_id": str(chat_id)},
            ).fetchone()
            if not chat_row:
                continue
            _, client_id, customer_phone, waba_number_id, prior_chat_state, ai_paused_until = chat_row

            # Batch text = inbound customer lines in this batch window only (opened_at .. sealed_at).
            msg_rows = conn.execute(
                text(
                    """
                    SELECT text
                    FROM inbox_messages
                    WHERE chat_id = CAST(:chat_id AS uuid)
                      AND direction = 'in'
                      AND sender = 'customer'
                      AND timestamp >= :opened_at
                      AND timestamp <= :sealed_at
                    ORDER BY timestamp ASC
                    LIMIT 200
                    """
                ),
                {"chat_id": str(chat_id), "opened_at": opened_at, "sealed_at": sealed_at},
            ).all()
            batch_text = "\n".join([r[0] for r in msg_rows]).strip()

            now_utc = datetime.now(tz=timezone.utc)
            pause_active = False
            if ai_paused_until is not None:
                ap = ai_paused_until
                if getattr(ap, "tzinfo", None) is None:
                    ap = ap.replace(tzinfo=timezone.utc)
                pause_active = ap > now_utc

            if prior_chat_state != "AI_ACTIVE" or pause_active:
                conn.execute(
                    text(
                        """
                        UPDATE inbox_inbound_batches
                        SET status='PROCESSED'
                        WHERE id=CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(batch_id)},
                )
                processed += 1
                continue

            if is_typing_lock_enabled(conn):
                typing_active, typing_user_id = has_active_agent_typing(conn, str(chat_id))
                if typing_active:
                    record_misfire_safe(
                        engine,
                        source="batch_processor",
                        reason="agent_typing_active",
                        client_id=str(client_id),
                        chat_id=str(chat_id),
                        batch_text_preview=batch_text[:500],
                        detail={
                            "batch_id": str(batch_id),
                            "typing_user_id": typing_user_id,
                        },
                    )
                    _emit_chat_event_notify(
                        conn,
                        client_id=str(client_id),
                        event="ai_skipped",
                        data={
                            "chat_id": str(chat_id),
                            "batch_id": str(batch_id),
                            "reason": "agent_typing_active",
                            "typing_user_id": typing_user_id,
                        },
                    )
                    conn.execute(
                        text(
                            """
                            UPDATE inbox_inbound_batches
                            SET status='PROCESSED'
                            WHERE id=CAST(:id AS uuid)
                            """
                        ),
                        {"id": str(batch_id)},
                    )
                    processed += 1
                    continue

            if lookup_customer_block(
                conn,
                client_id=str(client_id),
                customer_phone_e164=str(customer_phone),
            ):
                conn.execute(
                    text(
                        """
                        UPDATE inbox_inbound_batches
                        SET status='PROCESSED'
                        WHERE id=CAST(:id AS uuid)
                        """
                    ),
                    {"id": str(batch_id)},
                )
                processed += 1
                continue

            # Second-line paywall (Chat C): OPEN batch may still seal after Chat B gateway allowed ingest.
            limits_root = load_daily_inbound_limits_json(conn)
            crow = _fetch_client_row(conn, str(client_id))
            if crow:
                ent, trial_end = crow
                inbound_today = _fetch_inbound_usage_today(conn, str(client_id))
                block_reason, idem_suffix = second_line_paywall_block(
                    entitlement=ent,
                    trial_end=trial_end,
                    inbound_today=inbound_today,
                    limits_root=limits_root,
                )
                if block_reason:
                    idem = f"paywall:{block_reason}:{client_id}:{idem_suffix or 'na'}"[:512]
                    _enqueue_paywall_outbox(
                        conn,
                        client_id=str(client_id),
                        chat_id=str(chat_id),
                        to_phone=str(customer_phone),
                        from_wa_number_id=str(waba_number_id) if waba_number_id else None,
                        idempotency_key=idem,
                        body=load_paywall_reply(conn, block_reason),
                    )
                    conn.execute(
                        text(
                            """
                            UPDATE inbox_inbound_batches
                            SET status='PROCESSED'
                            WHERE id=CAST(:id AS uuid)
                            """
                        ),
                        {"id": str(batch_id)},
                    )
                    processed += 1
                    continue

            # Call AI engine (HTTP contract stable for batch_processor).
            ai: dict[str, Any] = {
                "action": "REPLY",
                "reply_text": "Hi!",
                "intent": "unknown",
                "routing_intent": "general",
            }
            trace_id = new_trace_id()
            ai_timeout = float(_settings.batch_ai_engine_timeout_seconds)
            t_ai = time.perf_counter()
            try:
                with httpx.Client(timeout=ai_timeout) as client:
                    r = client.post(
                        f"{AI_ENGINE_URL}/ai/respond",
                        json={
                            "client_id": str(client_id),
                            "chat_id": str(chat_id),
                            "batch_id": str(batch_id),
                            "customer_phone": str(customer_phone),
                            "batch_text": batch_text,
                        },
                        headers={"X-Trace-Id": trace_id},
                    )
                    r.raise_for_status()
                    raw_ai = r.json()
                    if isinstance(raw_ai, dict):
                        ai = apply_u2_strict_after_ai(raw_ai)
                    else:
                        ai = {"action": "HANDOFF", "handoff_reason": "ai_invalid_response"}
                record_trace_safe(
                    engine,
                    trace_id=trace_id,
                    service="batch_processor",
                    route="POST /ai/respond",
                    latency_ms=int((time.perf_counter() - t_ai) * 1000),
                    status="ok",
                    client_id=str(client_id),
                    chat_id=str(chat_id),
                    meta={"intent": ai.get("intent"), "action": ai.get("action")},
                )
            except Exception as exc:
                record_trace_safe(
                    engine,
                    trace_id=trace_id,
                    service="batch_processor",
                    route="POST /ai/respond",
                    latency_ms=int((time.perf_counter() - t_ai) * 1000),
                    status="error",
                    client_id=str(client_id),
                    chat_id=str(chat_id),
                    meta={"error": str(exc)[:500]},
                )
                record_misfire_safe(
                    engine,
                    source="batch_processor",
                    reason="ai_unavailable",
                    trace_id=trace_id,
                    client_id=str(client_id),
                    chat_id=str(chat_id),
                    batch_text_preview=batch_text[:500],
                    detail={"error": str(exc)[:500]},
                )
                ai = {"action": "HANDOFF", "handoff_reason": "ai_unavailable"}

            action = ai.get("action") or "REPLY"
            if action == "REPLY":
                reply_text = (ai.get("reply_text") or "").strip()
                if reply_text:
                    from_number_id = waba_number_id
                    if from_number_id:
                        conn.execute(
                            text(
                                """
                                INSERT INTO wa_outbox(
                                  client_id, chat_id, to_phone_e164, from_wa_number_id,
                                  kind, body_text, reply_to_batch_id, idempotency_key, status
                                )
                                VALUES (
                                  CAST(:client_id AS uuid), CAST(:chat_id AS uuid), :to_phone, CAST(:from_id AS uuid),
                                  'AI_REPLY', :body, CAST(:batch_id AS uuid), :idem, 'PENDING'
                                )
                                ON CONFLICT (idempotency_key) DO NOTHING
                                """
                            ),
                            {
                                "client_id": str(client_id),
                                "chat_id": str(chat_id),
                                "to_phone": str(customer_phone),
                                "from_id": str(from_number_id),
                                "body": reply_text,
                                "batch_id": str(batch_id),
                                "idem": f"ai:{chat_id}:{batch_id}",
                            },
                        )

            elif action in ("HANDOFF", "NEEDS_OWNER_DATA"):
                reason = str(
                    ai.get("handoff_reason")
                    or ai.get("risk_reason")
                    or ("needs_owner_data" if action == "NEEDS_OWNER_DATA" else "handoff")
                )[:4000]
                new_state = "WAITING_OWNER_DATA" if action == "NEEDS_OWNER_DATA" else "HUMAN_REQ"
                conn.execute(
                    text(
                        """
                        UPDATE inbox_chats
                        SET state = :st,
                            handoff_reason = :hr,
                            pending_since = COALESCE(pending_since, now())
                        WHERE id = CAST(:cid AS uuid)
                        """
                    ),
                    {"cid": str(chat_id), "hr": reason[:2000], "st": new_state},
                )
                _emit_chat_event_notify(
                    conn,
                    client_id=str(client_id),
                    event="chat_state_changed",
                    data={
                        "chat_id": str(chat_id),
                        "prior_state": str(prior_chat_state or "AI_ACTIVE"),
                        "state": new_state,
                        "reason": reason[:500],
                        "source": "batch_processor",
                        "ai_action": action,
                    },
                )
                try:
                    notify_handoff_states(
                        conn,
                        client_id=str(client_id),
                        chat_id=str(chat_id),
                        new_state=new_state,
                        reason=reason,
                        ai_action=action,
                    )
                except Exception:
                    # Never fail batch seal on notification insert (migration not applied, etc.).
                    pass

                if action == "NEEDS_OWNER_DATA":
                    customer_body = _load_needs_owner_customer_reply_text(conn).strip()
                    if waba_number_id and customer_body:
                        conn.execute(
                            text(
                                """
                                INSERT INTO wa_outbox(
                                  client_id, chat_id, to_phone_e164, from_wa_number_id,
                                  kind, body_text, reply_to_batch_id, idempotency_key, status
                                )
                                VALUES (
                                  CAST(:client_id AS uuid), CAST(:chat_id AS uuid), :to_phone, CAST(:from_id AS uuid),
                                  'AI_REPLY', :body, CAST(:batch_id AS uuid), :idem, 'PENDING'
                                )
                                ON CONFLICT (idempotency_key) DO NOTHING
                                """
                            ),
                            {
                                "client_id": str(client_id),
                                "chat_id": str(chat_id),
                                "to_phone": str(customer_phone),
                                "from_id": str(waba_number_id),
                                "body": customer_body,
                                "batch_id": str(batch_id),
                                "idem": f"needs_owner_customer:{chat_id}:{batch_id}",
                            },
                        )

            conn.execute(
                text(
                    """
                    UPDATE inbox_inbound_batches
                    SET status='PROCESSED'
                    WHERE id=CAST(:id AS uuid)
                    """
                ),
                {"id": str(batch_id)},
            )

            processed += 1

    _ = cfg
    return processed


def main() -> None:
    while True:
        try:
            n = run_once()
            # Sleep short when busy; longer when idle.
            time.sleep(0.25 if n > 0 else 1.0)
        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    main()

