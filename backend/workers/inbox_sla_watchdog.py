"""
Option C phase 4: owner-wait (4h re-alert, 8h apology) + agent SLA breach markers.

Run alongside batch_processor:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend\\workers\\inbox_sla_watchdog.py
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.config import settings
from backend.shared.db import engine
from backend.shared.inbox_notify import insert_notification, notify_owners_inbox_event, owner_user_ids_for_client
from backend.shared.inbox_sla_config import load_agent_sla_config, load_owner_wait_config
from backend.shared.ops_alerts import insert_ops_alert_event

log = logging.getLogger("inbox_sla_watchdog")


def _process_owner_wait_4h(conn: Connection, *, hours: int) -> int:
    rows = conn.execute(
        text(
            """
            SELECT c.id::text, c.client_id::text, c.customer_phone, c.handoff_reason
            FROM inbox_chats c
            WHERE c.state = 'WAITING_OWNER_DATA'
              AND c.pending_since IS NOT NULL
              AND c.owner_wait_4h_at IS NULL
              AND c.pending_since <= timezone('utc', now()) - (:h || ' hours')::interval
            LIMIT 50
            """
        ),
        {"h": int(hours)},
    ).all()
    n = 0
    for chat_id, client_id, phone, reason in rows:
        notify_owners_inbox_event(
            conn,
            client_id=str(client_id),
            chat_id=str(chat_id),
            title="Reminder: owner data still needed",
            body=f"{phone}: waiting {(reason or '')[:500]}",
            kind="inbox_owner_wait_4h",
            payload={"chat_id": chat_id, "customer_phone": phone, "hours": hours},
        )
        conn.execute(
            text(
                """
                UPDATE inbox_chats SET owner_wait_4h_at = timezone('utc', now())
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id},
        )
        n += 1
        log.info("owner_wait 4h re-alert chat=%s client=%s", chat_id, client_id)
    return n


def _enqueue_apology(
    conn: Connection,
    *,
    client_id: str,
    chat_id: str,
    customer_phone: str,
    waba_number_id: str | None,
    body: str,
) -> None:
    if not waba_number_id or not body.strip():
        return
    conn.execute(
        text(
            """
            INSERT INTO wa_outbox(
              client_id, chat_id, to_phone_e164, from_wa_number_id,
              kind, body_text, idempotency_key, status
            )
            VALUES (
              CAST(:client_id AS uuid), CAST(:chat_id AS uuid), :to_phone,
              CAST(:from_id AS uuid), 'AI_REPLY', :body,
              :idem, 'PENDING'
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """
        ),
        {
            "client_id": client_id,
            "chat_id": chat_id,
            "to_phone": customer_phone,
            "from_id": waba_number_id,
            "body": body.strip()[:4096],
            "idem": f"owner_wait_8h:{chat_id}",
        },
    )


def _process_owner_wait_8h(conn: Connection, *, hours: int, apology: str) -> int:
    rows = conn.execute(
        text(
            """
            SELECT c.id::text, c.client_id::text, c.customer_phone, c.handoff_reason,
                   c.waba_number::text
            FROM inbox_chats c
            WHERE c.state = 'WAITING_OWNER_DATA'
              AND c.pending_since IS NOT NULL
              AND c.owner_wait_8h_at IS NULL
              AND c.pending_since <= timezone('utc', now()) - (:h || ' hours')::interval
            LIMIT 20
            """
        ),
        {"h": int(hours)},
    ).all()
    n = 0
    for chat_id, client_id, phone, reason, waba_id in rows:
        _enqueue_apology(
            conn,
            client_id=str(client_id),
            chat_id=str(chat_id),
            customer_phone=str(phone),
            waba_number_id=str(waba_id) if waba_id else None,
            body=apology,
        )
        notify_owners_inbox_event(
            conn,
            client_id=str(client_id),
            chat_id=str(chat_id),
            title="8h: owner data overdue — customer apologized",
            body=f"{phone}: escalate and supply data",
            kind="inbox_owner_wait_8h",
            payload={"chat_id": chat_id, "customer_phone": phone},
        )
        dk = f"owner_wait_8h:{chat_id}"
        insert_ops_alert_event(
            conn,
            alert_type="OWNER_WAIT_8H",
            severity="warning",
            summary=f"Owner data wait >= {hours}h for {phone}",
            detail={"chat_id": chat_id, "client_id": client_id, "reason": (reason or "")[:500]},
            dedupe_key=dk,
        )
        conn.execute(
            text(
                """
                UPDATE inbox_chats SET owner_wait_8h_at = timezone('utc', now())
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id},
        )
        n += 1
        log.info("owner_wait 8h apology+alert chat=%s", chat_id)
    return n


def _process_agent_sla(conn: Connection, *, minutes: int) -> int:
    rows = conn.execute(
        text(
            """
            SELECT c.id::text, c.client_id::text, c.customer_phone, c.state,
                   c.assigned_agent_id::text
            FROM inbox_chats c
            WHERE c.state IN ('HUMAN_REQ', 'AGENT_ACTIVE')
              AND c.sla_breach_at IS NULL
              AND c.pending_since IS NOT NULL
              AND c.pending_since <= timezone('utc', now()) - (:m || ' minutes')::interval
              AND NOT EXISTS (
                SELECT 1 FROM inbox_messages m
                WHERE m.chat_id = c.id
                  AND m.direction = 'out'
                  AND m.sender = 'agent'
                  AND m.timestamp > COALESCE(c.last_customer_msg_at, c.pending_since)
              )
            LIMIT 50
            """
        ),
        {"m": int(minutes)},
    ).all()
    n = 0
    for chat_id, client_id, phone, state, agent_id in rows:
        now = datetime.now(tz=timezone.utc)
        conn.execute(
            text(
                """
                UPDATE inbox_chats SET sla_breach_at = timezone('utc', now())
                WHERE id = CAST(:cid AS uuid) AND sla_breach_at IS NULL
                """
            ),
            {"cid": chat_id},
        )
        title = "SLA breach: agent response overdue"
        body = f"{phone} ({state})"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "state": state,
            "customer_phone": phone,
            "sla_minutes": minutes,
        }
        notify_owners_inbox_event(
            conn,
            client_id=str(client_id),
            chat_id=str(chat_id),
            title=title,
            body=body,
            kind="inbox_sla_breach",
            payload=payload,
        )
        if agent_id:
            insert_notification(
                conn,
                client_id=str(client_id),
                recipient_user_id=str(agent_id),
                chat_id=str(chat_id),
                kind="inbox_sla_breach",
                title=title,
                body=body,
                payload=payload,
            )
        insert_ops_alert_event(
            conn,
            alert_type="INBOX_AGENT_SLA_BREACH",
            severity="warning",
            summary=f"Agent SLA {minutes}m breached for {phone}",
            detail={"chat_id": chat_id, "client_id": client_id, "state": state},
            dedupe_key=f"sla_breach:{chat_id}",
        )
        n += 1
        log.info("sla_breach chat=%s state=%s", chat_id, state)
    return n


def run_once() -> dict[str, int]:
    with engine.begin() as conn:
        ow = load_owner_wait_config(conn)
        sla = load_agent_sla_config(conn)
        return {
            "owner_4h": _process_owner_wait_4h(conn, hours=ow.realert_hours),
            "owner_8h": _process_owner_wait_8h(
                conn, hours=ow.apology_hours, apology=ow.apology_customer_reply
            ),
            "sla": _process_agent_sla(conn, minutes=sla.response_minutes),
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    interval = settings.inbox_sla_watchdog_sleep_seconds
    log.info("inbox_sla_watchdog started (interval=%ss)", interval)
    while True:
        try:
            stats = run_once()
            if any(stats.values()):
                log.info("tick %s", stats)
        except Exception:
            log.exception("inbox_sla_watchdog tick error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
