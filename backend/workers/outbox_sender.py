from __future__ import annotations

import os
import socket
import time

import httpx
from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.config import settings


INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()


def _meta_send(phone_number_id: str, to_phone: str, body: str) -> str:
    url = f"https://graph.facebook.com/{settings.meta_graph_version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.meta_access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": body}}
    with httpx.Client(timeout=20.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    # Expected: {"messages":[{"id":"wamid...."}]}
    msg_id = None
    for m in (data.get("messages") or []):
        if m.get("id"):
            msg_id = m["id"]
            break
    if not msg_id:
        raise RuntimeError("meta send: missing message id")
    return str(msg_id)


def run_once() -> int:
    """
    Phase D: this will send messages via Meta Cloud API.
    If META_ACCESS_TOKEN is not configured, it fails safely and retries.
    """
    sent = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, to_phone_e164, from_wa_number_id, body_text, attempt_count
                FROM wa_outbox
                WHERE status IN ('PENDING','FAILED') AND next_attempt_at <= now()
                ORDER BY next_attempt_at ASC
                LIMIT 25
                FOR UPDATE SKIP LOCKED
                """
            )
        ).all()

        for outbox_id, to_phone, from_wa_number_id, body_text, attempt_count in rows:
            # Mark SENDING
            conn.execute(
                text(
                    """
                    UPDATE wa_outbox
                    SET status='SENDING'
                    WHERE id=:id::uuid
                    """
                ),
                {"id": str(outbox_id)},
            )

            try:
                if not settings.meta_access_token:
                    raise RuntimeError("META_ACCESS_TOKEN not configured")

                phone_number_id = conn.execute(
                    text("SELECT meta_phone_number_id FROM wa_numbers WHERE id = :id::uuid"),
                    {"id": str(from_wa_number_id)},
                ).scalar()
                if not phone_number_id:
                    raise RuntimeError("wa_numbers.meta_phone_number_id missing")

                meta_message_id = _meta_send(str(phone_number_id), str(to_phone), str(body_text))
                conn.execute(
                    text(
                        """
                        UPDATE wa_outbox
                        SET status='SENT',
                            meta_message_id=:mid,
                            sent_at=now(),
                            last_error_code=NULL,
                            last_error_detail=NULL
                        WHERE id=:id::uuid
                        """
                    ),
                    {"id": str(outbox_id), "mid": meta_message_id},
                )
                sent += 1
            except Exception as e:
                # Exponential-ish backoff with cap, plus jitter later.
                next_seconds = min(300, 5 * (int(attempt_count) + 1))
                conn.execute(
                    text(
                        """
                        UPDATE wa_outbox
                        SET status='FAILED',
                            attempt_count = attempt_count + 1,
                            next_attempt_at = now() + (:s || ' seconds')::interval,
                            last_error_code = 'SEND_FAILED',
                            last_error_detail = :d
                        WHERE id=:id::uuid
                        """
                    ),
                    {"id": str(outbox_id), "s": next_seconds, "d": f"{type(e).__name__}: {e} ({INSTANCE_ID})"},
                )

    return sent


def main() -> None:
    while True:
        try:
            n = run_once()
            time.sleep(0.25 if n > 0 else 1.0)
        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    main()

