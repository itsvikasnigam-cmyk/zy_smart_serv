from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import text

from backend.shared.db import engine


@dataclass(frozen=True)
class DebounceConfig:
    debounce_seconds: int = 3
    max_debounce_seconds: int = 10


INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()
AI_ENGINE_URL = os.environ.get("AI_ENGINE_URL", "http://127.0.0.1:8083")


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
    - call AI engine stub
    - enqueue a single outbox message (idempotent)
    - mark batch PROCESSED

    NOTE (M3/M4 client_api): this worker is in a separate process. WS fan-out
    is the client_api DBPoller's responsibility — it picks up the new wa_outbox
    row (kind='AI_REPLY') and pushes ``message_new`` to subscribed agents. Do
    not import client_api from this worker. If you need lower-latency fan-out
    later, emit a Postgres ``NOTIFY 'chat_events'`` and have client_api LISTEN.
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
                    SELECT c.id, c.client_id, c.customer_phone, c.waba_number
                    FROM inbox_chats c
                    WHERE c.id = CAST(:chat_id AS uuid)
                    """
                ),
                {"chat_id": str(chat_id)},
            ).fetchone()
            if not chat_row:
                continue
            _, client_id, customer_phone, waba_number_id = chat_row

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

            # Call AI engine (stub)
            ai = {"action": "REPLY", "reply_text": "Hi!", "intent": "unknown", "routing_intent": "general"}
            try:
                with httpx.Client(timeout=10.0) as client:
                    r = client.post(
                        f"{AI_ENGINE_URL}/ai/respond",
                        json={
                            "client_id": str(client_id),
                            "chat_id": str(chat_id),
                            "batch_id": str(batch_id),
                            "customer_phone": str(customer_phone),
                            "batch_text": batch_text,
                        },
                    )
                    r.raise_for_status()
                    ai = r.json()
            except Exception:
                ai = {"action": "HANDOFF", "handoff_reason": "ai_unavailable"}

            # For now, only handle REPLY in worker; HANDOFF will be wired next.
            if ai.get("action") == "REPLY":
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

