from __future__ import annotations

"""Shared helpers for ``inbox_notifications`` + ``inbox_assignment_audit``.

Used by ``client_api`` (assignment flows) and ``batch_processor`` (HANDOFF /
NEEDS_OWNER_DATA) without importing FastAPI layers into the worker.
"""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def owner_user_ids_for_client(conn: Connection, client_id: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT id::text FROM api_users
            WHERE client_id = CAST(:cid AS uuid) AND role = 'owner'
            """
        ),
        {"cid": client_id},
    ).all()
    return [str(r[0]) for r in rows]


def _uuid_sql(name: str) -> str:
    """SQL fragment: NULL if bind is empty string, else uuid."""
    return f"CASE WHEN :{name} = '' THEN NULL ELSE CAST(:{name} AS uuid) END"


def insert_notification(
    conn: Connection,
    *,
    client_id: str,
    recipient_user_id: str,
    chat_id: str | None,
    kind: str,
    title: str,
    body: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[str, Any]:
    cid_chat = chat_id or ""
    row = conn.execute(
        text(
            f"""
            INSERT INTO inbox_notifications (
              client_id, recipient_user_id, chat_id, kind, title, body, payload
            )
            VALUES (
              CAST(:client AS uuid),
              CAST(:uid AS uuid),
              {_uuid_sql("cid_chat")},
              :kind,
              :title,
              :body,
              CAST(:payload AS jsonb)
            )
            RETURNING id::text, created_at
            """
        ),
        {
            "client": client_id,
            "uid": recipient_user_id,
            "cid_chat": cid_chat,
            "kind": kind,
            "title": title[:500],
            "body": body,
            "payload": json.dumps(payload or {}),
        },
    ).fetchone()
    return str(row[0]), row[1]


def insert_assignment_audit(
    conn: Connection,
    *,
    client_id: str,
    chat_id: str,
    assignment_id: str | None,
    event_type: str,
    actor_user_id: str | None,
    from_user_id: str | None,
    to_user_id: str | None,
    meta: dict[str, Any] | None = None,
) -> str:
    aid = conn.execute(
        text(
            f"""
            INSERT INTO inbox_assignment_audit (
              client_id, chat_id, assignment_id, event_type,
              actor_user_id, from_user_id, to_user_id, meta
            )
            VALUES (
              CAST(:client AS uuid),
              CAST(:chat AS uuid),
              {_uuid_sql("assign")},
              :etype,
              {_uuid_sql("actor")},
              {_uuid_sql("from_u")},
              {_uuid_sql("to_u")},
              CAST(:meta AS jsonb)
            )
            RETURNING id::text
            """
        ),
        {
            "client": client_id,
            "chat": chat_id,
            "assign": assignment_id or "",
            "etype": event_type[:80],
            "actor": actor_user_id or "",
            "from_u": from_user_id or "",
            "to_u": to_user_id or "",
            "meta": json.dumps(meta or {}),
        },
    ).scalar_one()
    return str(aid)


def notify_owners_inbox_event(
    conn: Connection,
    *,
    client_id: str,
    chat_id: str,
    title: str,
    body: str | None,
    kind: str,
    payload: dict[str, Any],
) -> list[str]:
    """Insert one notification row per owner (CC). Returns inserted ids."""
    ids: list[str] = []
    for oid in owner_user_ids_for_client(conn, client_id):
        nid, _ts = insert_notification(
            conn,
            client_id=client_id,
            recipient_user_id=oid,
            chat_id=chat_id,
            kind=kind,
            title=title,
            body=body,
            payload=payload,
        )
        ids.append(nid)
    return ids


def notify_handoff_states(
    conn: Connection,
    *,
    client_id: str,
    chat_id: str,
    new_state: str,
    reason: str,
    ai_action: str,
) -> list[str]:
    """When batch_processor moves chat to HUMAN_REQ or WAITING_OWNER_DATA, notify owners."""
    title = "Chat needs attention" if new_state == "HUMAN_REQ" else "Waiting for owner data"
    body = (reason or "")[:2000]
    payload = {"chat_id": chat_id, "state": new_state, "ai_action": ai_action, "reason": reason[:500]}
    return notify_owners_inbox_event(
        conn,
        client_id=client_id,
        chat_id=chat_id,
        title=title,
        body=body,
        kind="inbox_state_handoff",
        payload=payload,
    )
