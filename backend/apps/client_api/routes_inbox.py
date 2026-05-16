from __future__ import annotations

"""Inbox + assignment + typing + agent reply routes for client_api.

Blueprint ``inbox_chats.state`` values (CHECK enforced by migration ``0008``):

    AI_ACTIVE            — AI is responsible
    HUMAN_REQ            — needs a human agent (unassigned queue)
    WAITING_OWNER_DATA   — AI needs owner-supplied data before continuing
    AGENT_ACTIVE         — an agent owns the conversation
    CLOSED               — resolved / archived

``chat_assignments.status`` still uses ACTIVE / REASSIGNED / RESOLVED (assignment row lifecycle, not chat state).

Invariants:
- ``chat_assignments`` has a partial UNIQUE on (chat_id) WHERE status='ACTIVE'.
- Switching agents → end ACTIVE row (status='REASSIGNED') then insert a new ACTIVE row, all within one transaction.
"""

import json
import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend.shared.config import settings
from backend.shared.db import engine
from backend.shared.inbox_notify import (
    insert_assignment_audit,
    insert_notification,
    owner_user_ids_for_client,
)

from .auth import ROLE_AGENT, ROLE_OWNER, ROLE_SUPER_ADMIN
from .deps import CurrentUser, assert_role_in, get_current_user, resolve_client_scope
from .events import (
    EVENT_ASSIGNMENT_CHANGED,
    EVENT_CHAT_STATE_CHANGED,
    EVENT_MESSAGE_NEW,
    EVENT_TYPING,
    hub,
)
from .models import (
    AssignmentOut,
    AssignRequest,
    ChatDetail,
    ChatList,
    ChatListItem,
    EscalateRequest,
    LEGAL_CHAT_STATES,
    MessageOut,
    DevTestNotificationOut,
    NotificationList,
    NotificationOut,
    ReplyRequest,
    ReplyResponse,
    ResolveRequest,
    TypingRequest,
    UnassignRequest,
)

router = APIRouter(tags=["inbox"], prefix="/inbox")


# ----------------------- helpers -----------------------


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


_IDEM_CLIENT_KEY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _parse_client_idempotency_key(raw: str | None) -> str | None:
    """Optional client key for safe POST /reply retries (``Idempotency-Key`` header)."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    if not _IDEM_CLIENT_KEY_RE.fullmatch(s):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must be 1-128 characters: letters, digits, underscore, hyphen",
        )
    return s


def _load_chat(conn: Connection, chat_id: str, client_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT id::text, client_id::text, customer_phone, state, assigned_agent_id::text,
                   last_customer_msg_at, last_outbound_at, created_at, waba_number::text,
                   ai_paused_until
            FROM inbox_chats
            WHERE id = CAST(:cid AS uuid) AND client_id = CAST(:client AS uuid)
            FOR UPDATE
            """
        ),
        {"cid": chat_id, "client": client_id},
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "client_id": row[1],
        "customer_phone": row[2],
        "state": row[3],
        "assigned_agent_id": row[4],
        "last_customer_msg_at": row[5],
        "last_outbound_at": row[6],
        "created_at": row[7],
        "waba_number": row[8],
        "ai_paused_until": row[9],
    }


def _to_list_item(row: dict[str, Any]) -> ChatListItem:
    return ChatListItem(
        id=row["id"],
        client_id=row["client_id"],
        customer_phone=row["customer_phone"],
        state=row["state"],
        assigned_agent_id=row["assigned_agent_id"],
        last_customer_msg_at=row["last_customer_msg_at"],
        last_outbound_at=row["last_outbound_at"],
        created_at=row["created_at"],
        last_message_preview=row.get("last_message_preview"),
        ai_paused_until=row.get("ai_paused_until"),
    )


def _active_assignment(conn: Connection, chat_id: str) -> dict[str, Any] | None:
    r = conn.execute(
        text(
            """
            SELECT id::text, chat_id::text, assigned_to_user_id::text, assigned_by_user_id::text,
                   reason, note, status, created_at, ended_at
            FROM chat_assignments
            WHERE chat_id = CAST(:cid AS uuid) AND status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {"cid": chat_id},
    ).fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "chat_id": r[1],
        "assigned_to_user_id": r[2],
        "assigned_by_user_id": r[3],
        "reason": r[4],
        "note": r[5],
        "status": r[6],
        "created_at": r[7],
        "ended_at": r[8],
    }


def _assignment_out(a: dict[str, Any]) -> AssignmentOut:
    return AssignmentOut(
        id=a["id"],
        chat_id=a["chat_id"],
        assigned_to_user_id=a["assigned_to_user_id"],
        assigned_by_user_id=a["assigned_by_user_id"],
        reason=a["reason"],
        note=a["note"],
        status=a["status"],
        created_at=a["created_at"],
        ended_at=a["ended_at"],
    )


def _end_active_assignment(
    conn: Connection,
    *,
    chat_id: str,
    new_status: str = "REASSIGNED",
) -> dict[str, Any] | None:
    """End the (at most one) ACTIVE assignment for a chat. Returns the prior row dict or None."""
    if new_status not in ("REASSIGNED", "RESOLVED"):
        raise ValueError(f"invalid terminal status: {new_status}")
    r = conn.execute(
        text(
            """
            UPDATE chat_assignments
            SET status = :ns, ended_at = now()
            WHERE chat_id = CAST(:cid AS uuid) AND status = 'ACTIVE'
            RETURNING id::text, assigned_to_user_id::text
            """
        ),
        {"cid": chat_id, "ns": new_status},
    ).fetchone()
    if not r:
        return None
    return {"id": r[0], "assigned_to_user_id": r[1]}


def _validate_assignee(conn: Connection, *, user_id: str, client_id: str) -> dict[str, Any]:
    if not _is_uuid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid user_id")
    row = conn.execute(
        text(
            """
            SELECT id::text, client_id::text, role, name, email
            FROM api_users
            WHERE id = CAST(:uid AS uuid)
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignee not found")
    if row[1] != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="assignee belongs to a different client",
        )
    if row[2] not in (ROLE_OWNER, ROLE_AGENT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assignee must be owner or agent",
        )
    return {"id": row[0], "client_id": row[1], "role": row[2], "name": row[3], "email": row[4]}


def _publish_state_change(client_id: str, chat_id: str, prior: str | None, new: str) -> None:
    if prior == new:
        return
    hub.publish(
        client_id,
        EVENT_CHAT_STATE_CHANGED,
        {"chat_id": chat_id, "prior_state": prior, "state": new},
    )


def _normalize_legacy_state_filter(state: str | None) -> str | None:
    """Map pre-0008 filter values for backward-compatible clients."""
    if state is None:
        return None
    s = state.strip()
    if s == "PENDING_AGENT":
        return "HUMAN_REQ"
    if s == "RESOLVED":
        return "CLOSED"
    return s


def _validate_state_filter(state: str) -> None:
    if state not in LEGAL_CHAT_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid state filter; use one of: {', '.join(LEGAL_CHAT_STATES)}",
        )


def _coerce_jsonb_int_cfg(value: Any, default: int) -> int:
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


def _pause_hours_agent_reply(conn: Connection, client_id: str) -> int:
    """Hours to extend ``ai_paused_until`` after an agent reply (Starter vs default from ops_runtime_config)."""
    row = conn.execute(
        text("SELECT entitlement_plan FROM api_clients WHERE id = CAST(:c AS uuid)"),
        {"c": client_id},
    ).fetchone()
    plan = (str(row[0]).lower() if row and row[0] else "trial")
    key = (
        "inbox.agent_reply_pause_hours_starter"
        if plan == "starter"
        else "inbox.agent_reply_pause_hours_default"
    )
    raw = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": key},
    ).scalar_one_or_none()
    return _coerce_jsonb_int_cfg(raw, 24)


# ----------------------- list / detail -----------------------


@router.get("/chats", response_model=ChatList)
def list_chats(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
    state: Annotated[
        str | None,
        Query(
            description=(
                "Filter by blueprint state: AI_ACTIVE|HUMAN_REQ|WAITING_OWNER_DATA|"
                "AGENT_ACTIVE|CLOSED. Legacy aliases PENDING_AGENT→HUMAN_REQ, RESOLVED→CLOSED."
            )
        ),
    ] = None,
    human_queue: Annotated[
        bool,
        Query(description="If true, restrict to HUMAN_REQ or WAITING_OWNER_DATA (needs-human queue)."),
    ] = False,
    assigned: Annotated[
        str | None,
        Query(description="'me' | 'unassigned' | a user_id"),
    ] = None,
    q: Annotated[str | None, Query(description="Substring match on customer_phone")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ChatList:
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    params: dict[str, Any] = {"cid": scope, "lim": limit}
    where = ["c.client_id = CAST(:cid AS uuid)"]
    if human_queue:
        where.append("c.state IN ('HUMAN_REQ','WAITING_OWNER_DATA')")
    elif state and str(state).strip():
        st = _normalize_legacy_state_filter(state.strip())
        _validate_state_filter(st)
        where.append("c.state = :state")
        params["state"] = st
    if assigned == "me":
        where.append("c.assigned_agent_id = CAST(:me AS uuid)")
        params["me"] = user.id
    elif assigned == "unassigned":
        where.append("c.assigned_agent_id IS NULL")
    elif assigned:
        if not _is_uuid(assigned):
            raise HTTPException(status_code=400, detail="invalid 'assigned' value")
        where.append("c.assigned_agent_id = CAST(:aid AS uuid)")
        params["aid"] = assigned
    if q:
        where.append("c.customer_phone ILIKE :qpat")
        params["qpat"] = f"%{q}%"

    sql = f"""
        SELECT c.id::text, c.client_id::text, c.customer_phone, c.state,
               c.assigned_agent_id::text, c.last_customer_msg_at, c.last_outbound_at, c.created_at,
               c.ai_paused_until,
               (SELECT text FROM inbox_messages
                  WHERE chat_id = c.id ORDER BY timestamp DESC LIMIT 1) AS last_preview
        FROM inbox_chats c
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(c.last_customer_msg_at, c.created_at) DESC
        LIMIT :lim
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    items = [
        ChatListItem(
            id=r[0],
            client_id=r[1],
            customer_phone=r[2],
            state=r[3],
            assigned_agent_id=r[4],
            last_customer_msg_at=r[5],
            last_outbound_at=r[6],
            created_at=r[7],
            ai_paused_until=r[8],
            last_message_preview=r[9],
        )
        for r in rows
    ]
    return ChatList(items=items)


@router.get("/chats/{chat_id}", response_model=ChatDetail)
def chat_detail(
    chat_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
    message_limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ChatDetail:
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")
    scope = resolve_client_scope(user, explicit_client_id=client_id)

    with engine.begin() as conn:
        chat = conn.execute(
            text(
                """
                SELECT id::text, client_id::text, customer_phone, state, assigned_agent_id::text,
                       last_customer_msg_at, last_outbound_at, created_at, ai_paused_until
                FROM inbox_chats
                WHERE id = CAST(:cid AS uuid) AND client_id = CAST(:client AS uuid)
                """
            ),
            {"cid": chat_id, "client": scope},
        ).fetchone()
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")

        msg_rows = conn.execute(
            text(
                """
                SELECT id::text, chat_id::text, direction, sender, text, timestamp, meta_msg_id,
                       'inbox_messages' AS source, NULL::text AS outbox_status, NULL::text AS outbox_kind
                FROM inbox_messages
                WHERE chat_id = CAST(:cid AS uuid)
                UNION ALL
                SELECT id::text, chat_id::text, 'out' AS direction,
                       CASE kind
                         WHEN 'AI_REPLY' THEN 'ai'
                         WHEN 'AGENT_REPLY' THEN 'agent'
                         WHEN 'OWNER_ALERT' THEN 'system'
                         ELSE 'system'
                       END AS sender,
                       body_text AS text,
                       COALESCE(sent_at, created_at) AS timestamp,
                       meta_message_id AS meta_msg_id,
                       'wa_outbox' AS source, status AS outbox_status, kind AS outbox_kind
                FROM wa_outbox
                WHERE chat_id = CAST(:cid AS uuid)
                  AND kind IN ('AI_REPLY','OWNER_ALERT')
                ORDER BY timestamp ASC
                LIMIT :lim
                """
            ),
            {"cid": chat_id, "lim": message_limit},
        ).all()
        messages = [
            MessageOut(
                id=r[0],
                chat_id=r[1],
                direction=r[2],
                sender=r[3],
                text=r[4],
                timestamp=r[5],
                meta_msg_id=r[6],
                source=r[7],
                outbox_status=r[8],
                outbox_kind=r[9],
            )
            for r in msg_rows
        ]

        pending_rows = conn.execute(
            text(
                """
                SELECT id::text, chat_id::text, body_text, kind, status, created_at, meta_message_id
                FROM wa_outbox
                WHERE chat_id = CAST(:cid AS uuid)
                  AND status IN ('PENDING','SENDING','FAILED')
                ORDER BY created_at ASC
                """
            ),
            {"cid": chat_id},
        ).all()
        pending = [
            MessageOut(
                id=r[0],
                chat_id=r[1],
                direction="out",
                sender={"AI_REPLY": "ai", "AGENT_REPLY": "agent"}.get(r[3], "system"),  # type: ignore[arg-type]
                text=r[2],
                timestamp=r[5],
                meta_msg_id=r[6],
                source="wa_outbox",
                outbox_status=r[4],
                outbox_kind=r[3],
            )
            for r in pending_rows
        ]

        active = _active_assignment(conn, chat_id)

    item = ChatListItem(
        id=chat[0],
        client_id=chat[1],
        customer_phone=chat[2],
        state=chat[3],
        assigned_agent_id=chat[4],
        last_customer_msg_at=chat[5],
        last_outbound_at=chat[6],
        created_at=chat[7],
        ai_paused_until=chat[8],
    )
    return ChatDetail(
        chat=item,
        assignment=_assignment_out(active) if active else None,
        messages=messages,
        pending_outbound=pending,
    )


# ----------------------- notifications -----------------------


def _parse_notification_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    unread_only: Annotated[
        bool,
        Query(description="If true, only notifications where read_at IS NULL."),
    ] = False,
) -> NotificationList:
    """In-app notifications for the signed-in user within the scoped client."""
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    params: dict[str, Any] = {"cid": scope, "uid": user.id, "lim": limit}
    where = [
        "n.client_id = CAST(:cid AS uuid)",
        "n.recipient_user_id = CAST(:uid AS uuid)",
    ]
    if unread_only:
        where.append("n.read_at IS NULL")
    sql = f"""
        SELECT n.id::text, n.client_id::text, n.recipient_user_id::text, n.chat_id::text,
               n.kind, n.title, n.body, n.payload, n.read_at, n.created_at
        FROM inbox_notifications n
        WHERE {' AND '.join(where)}
        ORDER BY n.created_at DESC
        LIMIT :lim
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    items = [
        NotificationOut(
            id=r[0],
            client_id=r[1],
            recipient_user_id=r[2],
            chat_id=r[3],
            kind=r[4],
            title=r[5],
            body=r[6],
            payload=_parse_notification_payload(r[7]),
            read_at=r[8],
            created_at=r[9],
        )
        for r in rows
    ]
    return NotificationList(items=items)


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> dict[str, Any]:
    """Mark a single notification row read (idempotent for the recipient)."""
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    if not _is_uuid(notification_id):
        raise HTTPException(status_code=400, detail="invalid notification_id")
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                UPDATE inbox_notifications
                SET read_at = COALESCE(read_at, now())
                WHERE id = CAST(:nid AS uuid)
                  AND client_id = CAST(:cid AS uuid)
                  AND recipient_user_id = CAST(:uid AS uuid)
                RETURNING id::text
                """
            ),
            {"nid": notification_id, "cid": scope, "uid": user.id},
        ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="notification not found")
    return {"ok": True}


@router.post("/notifications/dev-test", response_model=DevTestNotificationOut)
def create_dev_test_notification(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> DevTestNotificationOut:
    """Insert one unread notification for the signed-in user (``APP_ENV=dev`` only)."""
    if settings.app_env != "dev":
        raise HTTPException(status_code=404, detail="not found")
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    chat_id: str | None = None
    with engine.begin() as conn:
        chat_row = conn.execute(
            text(
                """
                SELECT id::text FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"cid": scope},
        ).fetchone()
        if chat_row:
            chat_id = chat_row[0]
        nid, _ts = insert_notification(
            conn,
            client_id=scope,
            recipient_user_id=user.id,
            chat_id=chat_id,
            kind="dev_test",
            title="Test alert (dev)",
            body="Practice notification from your local app. Tap to mark read and open the chat.",
            payload={"dev": True, "source": "POST /inbox/notifications/dev-test"},
        )
    return DevTestNotificationOut(
        id=nid,
        chat_id=chat_id,
        message="Test notification created. Tap Refresh list if it does not appear within a few seconds.",
    )


# ----------------------- assignment -----------------------


def _do_assign(
    *,
    actor: CurrentUser,
    client_scope: str,
    chat_id: str,
    body: AssignRequest,
    require_no_active: bool,
) -> AssignmentOut:
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")
    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, client_scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
        assignee = _validate_assignee(conn, user_id=body.user_id, client_id=client_scope)
        current = _active_assignment(conn, chat_id)
        if require_no_active and current is not None:
            if current["assigned_to_user_id"] == assignee["id"]:
                raise HTTPException(status_code=409, detail="chat already assigned to this user")
            raise HTTPException(status_code=409, detail="chat already has an active assignment; use /reassign")
        if current and current["assigned_to_user_id"] == assignee["id"]:
            return _assignment_out(current)
        prior_assignee_id = current["assigned_to_user_id"] if current else None
        evt = "REASSIGNED" if prior_assignee_id else "ASSIGNED"
        if current:
            _end_active_assignment(conn, chat_id=chat_id, new_status="REASSIGNED")
        try:
            row = conn.execute(
                text(
                    """
                    INSERT INTO chat_assignments (
                        chat_id, client_id, assigned_to_user_id, assigned_by_user_id,
                        reason, note, status
                    )
                    VALUES (
                        CAST(:cid AS uuid), CAST(:client AS uuid), CAST(:to AS uuid), CAST(:by AS uuid),
                        :reason, :note, 'ACTIVE'
                    )
                    RETURNING id::text, chat_id::text, assigned_to_user_id::text,
                              assigned_by_user_id::text, reason, note, status, created_at, ended_at
                    """
                ),
                {
                    "cid": chat_id,
                    "client": client_scope,
                    "to": assignee["id"],
                    "by": actor.id,
                    "reason": body.reason,
                    "note": body.note,
                },
            ).fetchone()
        except IntegrityError as e:
            raise HTTPException(status_code=409, detail="conflicting assignment") from e

        conn.execute(
            text(
                """
                UPDATE inbox_chats
                SET assigned_agent_id = CAST(:to AS uuid),
                    state = 'AGENT_ACTIVE',
                    handoff_reason = COALESCE(:reason, handoff_reason)
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"to": assignee["id"], "cid": chat_id, "reason": body.reason},
        )

        insert_assignment_audit(
            conn,
            client_id=client_scope,
            chat_id=chat_id,
            assignment_id=row[0],
            event_type=evt,
            actor_user_id=actor.id,
            from_user_id=prior_assignee_id,
            to_user_id=assignee["id"],
            meta={
                "reason": body.reason,
                "note": body.note,
                "customer_phone": chat.get("customer_phone"),
            },
        )
        phone = (str(chat.get("customer_phone") or "")).strip()
        title_asg = "You were assigned a chat"
        body_asg = phone or None
        insert_notification(
            conn,
            client_id=client_scope,
            recipient_user_id=assignee["id"],
            chat_id=chat_id,
            kind="inbox_assigned",
            title=title_asg,
            body=body_asg,
            payload={"chat_id": chat_id, "assignment_id": row[0], "event": evt.lower()},
        )
        title_cc = f"Chat assigned: {phone}" if phone else "Chat assigned"
        for oid in owner_user_ids_for_client(conn, client_scope):
            if oid == assignee["id"]:
                continue
            insert_notification(
                conn,
                client_id=client_scope,
                recipient_user_id=oid,
                chat_id=chat_id,
                kind="inbox_assignment_owner_cc",
                title=title_cc,
                body=body_asg,
                payload={
                    "chat_id": chat_id,
                    "assignment_id": row[0],
                    "assignee_user_id": assignee["id"],
                    "event": evt.lower(),
                },
            )

    a = {
        "id": row[0],
        "chat_id": row[1],
        "assigned_to_user_id": row[2],
        "assigned_by_user_id": row[3],
        "reason": row[4],
        "note": row[5],
        "status": row[6],
        "created_at": row[7],
        "ended_at": row[8],
    }
    hub.publish(
        client_scope,
        EVENT_ASSIGNMENT_CHANGED,
        {
            "chat_id": chat_id,
            "assignment_id": a["id"],
            "assigned_to_user_id": a["assigned_to_user_id"],
            "assigned_by_user_id": a["assigned_by_user_id"],
            "reason": a["reason"],
            "status": a["status"],
            "prior_assigned_to_user_id": prior_assignee_id,
        },
    )
    _publish_state_change(client_scope, chat_id, chat["state"], "AGENT_ACTIVE")
    return _assignment_out(a)


@router.post("/chats/{chat_id}/assign", response_model=AssignmentOut)
def assign(
    chat_id: str,
    body: AssignRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> AssignmentOut:
    assert_role_in(user, (ROLE_OWNER, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    return _do_assign(actor=user, client_scope=scope, chat_id=chat_id, body=body, require_no_active=True)


@router.post("/chats/{chat_id}/reassign", response_model=AssignmentOut)
def reassign(
    chat_id: str,
    body: AssignRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> AssignmentOut:
    assert_role_in(user, (ROLE_OWNER, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    return _do_assign(actor=user, client_scope=scope, chat_id=chat_id, body=body, require_no_active=False)


@router.post("/chats/{chat_id}/unassign")
def unassign(
    chat_id: str,
    body: UnassignRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> dict[str, Any]:
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")

    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
        current = _active_assignment(conn, chat_id)
        if current is None:
            return {"ok": True, "changed": False, "state": chat["state"]}

        # Agents may only unassign their own chats.
        if user.role == ROLE_AGENT and current["assigned_to_user_id"] != user.id:
            raise HTTPException(status_code=403, detail="agents may only unassign their own chats")

        prior_assignee = current["assigned_to_user_id"]
        phone = (str(chat.get("customer_phone") or "")).strip()
        _end_active_assignment(conn, chat_id=chat_id, new_status="REASSIGNED")
        conn.execute(
            text(
                """
                UPDATE inbox_chats
                SET assigned_agent_id = NULL,
                    state = 'HUMAN_REQ',
                    handoff_reason = COALESCE(:reason, handoff_reason)
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id, "reason": body.reason},
        )
        insert_assignment_audit(
            conn,
            client_id=scope,
            chat_id=chat_id,
            assignment_id=current["id"],
            event_type="UNASSIGNED",
            actor_user_id=user.id,
            from_user_id=prior_assignee,
            to_user_id=None,
            meta={"reason": body.reason, "customer_phone": phone},
        )
        title_prev = "You were unassigned from a chat"
        body_prev = phone or None
        insert_notification(
            conn,
            client_id=scope,
            recipient_user_id=prior_assignee,
            chat_id=chat_id,
            kind="inbox_unassigned",
            title=title_prev,
            body=body_prev,
            payload={"chat_id": chat_id, "assignment_id": current["id"]},
        )
        title_cc = f"Chat unassigned: {phone}" if phone else "Chat unassigned"
        for oid in owner_user_ids_for_client(conn, scope):
            if oid == prior_assignee:
                continue
            insert_notification(
                conn,
                client_id=scope,
                recipient_user_id=oid,
                chat_id=chat_id,
                kind="inbox_assignment_owner_cc",
                title=title_cc,
                body=body_prev,
                payload={"chat_id": chat_id, "prior_assignee_user_id": prior_assignee},
            )

    hub.publish(
        scope,
        EVENT_ASSIGNMENT_CHANGED,
        {
            "chat_id": chat_id,
            "assignment_id": current["id"],
            "assigned_to_user_id": None,
            "prior_assigned_to_user_id": current["assigned_to_user_id"],
            "assigned_by_user_id": user.id,
            "reason": body.reason,
            "status": "REASSIGNED",
        },
    )
    _publish_state_change(scope, chat_id, chat["state"], "HUMAN_REQ")
    return {"ok": True, "changed": True, "state": "HUMAN_REQ"}


@router.post("/chats/{chat_id}/escalate")
def escalate(
    chat_id: str,
    body: EscalateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> dict[str, Any]:
    """Escalate a chat from AI/auto handling to humans.

    - If ``to_user_id`` is provided: behaves like reassign (assigns to that user
      and sets state=AGENT_ACTIVE).
    - Otherwise: ends any active assignment and sets state=HUMAN_REQ so any
      agent can pick it up.
    """
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    if body.to_user_id:
        return _do_assign(  # type: ignore[return-value]
            actor=user,
            client_scope=scope,
            chat_id=chat_id,
            body=AssignRequest(user_id=body.to_user_id, reason=body.reason or "escalated", note=None),
            require_no_active=False,
        ).model_dump()

    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")
    current: dict[str, Any] | None = None
    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
        current = _active_assignment(conn, chat_id)
        prior_assignee = current["assigned_to_user_id"] if current else None
        phone = (str(chat.get("customer_phone") or "")).strip()
        if current:
            _end_active_assignment(conn, chat_id=chat_id, new_status="REASSIGNED")
        conn.execute(
            text(
                """
                UPDATE inbox_chats
                SET assigned_agent_id = NULL,
                    state = 'HUMAN_REQ',
                    handoff_reason = COALESCE(:reason, handoff_reason),
                    pending_since = COALESCE(pending_since, now())
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id, "reason": body.reason or "escalated"},
        )
        insert_assignment_audit(
            conn,
            client_id=scope,
            chat_id=chat_id,
            assignment_id=current["id"] if current else None,
            event_type="ESCALATED_TO_QUEUE",
            actor_user_id=user.id,
            from_user_id=prior_assignee,
            to_user_id=None,
            meta={"reason": body.reason or "escalated", "customer_phone": phone},
        )
        reason_txt = body.reason or "escalated"
        if prior_assignee:
            title_prev = "Chat escalated to human queue"
            body_prev = f"{phone}\n{reason_txt}".strip() if phone else reason_txt
            insert_notification(
                conn,
                client_id=scope,
                recipient_user_id=prior_assignee,
                chat_id=chat_id,
                kind="inbox_escalated",
                title=title_prev,
                body=body_prev,
                payload={"chat_id": chat_id, "reason": reason_txt},
            )
        title_cc = f"Chat escalated: {phone}" if phone else "Chat escalated to human queue"
        body_cc = reason_txt
        for oid in owner_user_ids_for_client(conn, scope):
            if prior_assignee and oid == prior_assignee:
                continue
            insert_notification(
                conn,
                client_id=scope,
                recipient_user_id=oid,
                chat_id=chat_id,
                kind="inbox_escalated_owner_cc",
                title=title_cc,
                body=body_cc,
                payload={"chat_id": chat_id, "reason": reason_txt},
            )

    if current:
        hub.publish(
            scope,
            EVENT_ASSIGNMENT_CHANGED,
            {
                "chat_id": chat_id,
                "assignment_id": current["id"],
                "assigned_to_user_id": None,
                "prior_assigned_to_user_id": current["assigned_to_user_id"],
                "assigned_by_user_id": user.id,
                "reason": body.reason or "escalated",
                "status": "REASSIGNED",
            },
        )
    _publish_state_change(scope, chat_id, chat["state"], "HUMAN_REQ")
    return {"ok": True, "state": "HUMAN_REQ"}


@router.post("/chats/{chat_id}/resolve")
def resolve_chat(
    chat_id: str,
    body: ResolveRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> dict[str, Any]:
    """Mark a chat closed (blueprint ``CLOSED``): clears assignee and ends any ACTIVE assignment."""
    assert_role_in(user, (ROLE_OWNER, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")

    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
        if chat["state"] == "CLOSED":
            return {"ok": True, "changed": False, "state": "CLOSED"}

        current = _active_assignment(conn, chat_id)
        prior_assignee = current["assigned_to_user_id"] if current else None
        ended_id = None
        if current:
            ended = _end_active_assignment(conn, chat_id=chat_id, new_status="RESOLVED")
            ended_id = ended["id"] if ended else current["id"]
        phone = (str(chat.get("customer_phone") or "")).strip()
        reason_txt = (body.reason or "").strip() or None
        conn.execute(
            text(
                """
                UPDATE inbox_chats
                SET state = 'CLOSED',
                    assigned_agent_id = NULL,
                    handoff_reason = COALESCE(:reason, handoff_reason)
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id, "reason": body.reason},
        )
        insert_assignment_audit(
            conn,
            client_id=scope,
            chat_id=chat_id,
            assignment_id=ended_id,
            event_type="CHAT_RESOLVED",
            actor_user_id=user.id,
            from_user_id=prior_assignee,
            to_user_id=None,
            meta={"reason": body.reason, "customer_phone": phone},
        )
        notified: set[str] = set()
        if prior_assignee:
            title_a = "Chat you were on was resolved"
            body_a = phone or reason_txt
            insert_notification(
                conn,
                client_id=scope,
                recipient_user_id=prior_assignee,
                chat_id=chat_id,
                kind="inbox_chat_resolved",
                title=title_a,
                body=body_a,
                payload={"chat_id": chat_id, "reason": body.reason},
            )
            notified.add(prior_assignee)
        title_o = f"Chat resolved: {phone}" if phone else "Chat resolved"
        body_o = reason_txt
        for oid in owner_user_ids_for_client(conn, scope):
            if oid in notified:
                continue
            insert_notification(
                conn,
                client_id=scope,
                recipient_user_id=oid,
                chat_id=chat_id,
                kind="inbox_chat_resolved_owner_cc",
                title=title_o,
                body=body_o,
                payload={"chat_id": chat_id, "reason": body.reason},
            )

    if current:
        hub.publish(
            scope,
            EVENT_ASSIGNMENT_CHANGED,
            {
                "chat_id": chat_id,
                "assignment_id": current["id"],
                "assigned_to_user_id": None,
                "prior_assigned_to_user_id": prior_assignee,
                "assigned_by_user_id": user.id,
                "reason": body.reason or "resolved",
                "status": "RESOLVED",
            },
        )
    _publish_state_change(scope, chat_id, chat["state"], "CLOSED")
    return {"ok": True, "changed": True, "state": "CLOSED"}


# ----------------------- typing -----------------------


@router.post("/chats/{chat_id}/typing")
def typing(
    chat_id: str,
    body: TypingRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
) -> dict[str, Any]:
    """Heartbeat-style presence indicator.

    The row in ``chat_presence`` has TTL ``expires_at`` (refresh by re-posting).
    Sending ``state='stopped'`` removes the row immediately. WS subscribers see
    a ``typing`` event in either case.
    """
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")

    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")

        if body.state == "stopped":
            conn.execute(
                text(
                    """
                    DELETE FROM chat_presence
                    WHERE chat_id = CAST(:cid AS uuid)
                      AND user_id = CAST(:uid AS uuid)
                      AND state = 'typing'
                    """
                ),
                {"cid": chat_id, "uid": user.id},
            )
            expires_at = None
        else:
            row = conn.execute(
                text(
                    """
                    INSERT INTO chat_presence (chat_id, user_id, state, expires_at)
                    VALUES (
                        CAST(:cid AS uuid),
                        CAST(:uid AS uuid),
                        'typing',
                        now() + (:ttl || ' seconds')::interval
                    )
                    ON CONFLICT (chat_id, user_id, state)
                    DO UPDATE SET expires_at = EXCLUDED.expires_at,
                                  updated_at = now()
                    RETURNING expires_at
                    """
                ),
                {"cid": chat_id, "uid": user.id, "ttl": body.ttl_seconds},
            ).fetchone()
            expires_at = row[0] if row else None

    hub.publish(
        scope,
        EVENT_TYPING,
        {
            "chat_id": chat_id,
            "user_id": user.id,
            "state": body.state,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    return {"ok": True, "expires_at": expires_at.isoformat() if expires_at else None}


# ----------------------- agent reply -----------------------


@router.post("/chats/{chat_id}/reply", response_model=ReplyResponse)
def reply(
    chat_id: str,
    body: ReplyRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    client_id: Annotated[str | None, Query(description="Required for super_admin")] = None,
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReplyResponse:
    """Send an agent reply.

    Mirrors the message into ``inbox_messages`` (direction='out', sender='agent')
    AND enqueues a ``wa_outbox`` row with kind='AGENT_REPLY' for the outbox sender
    to deliver to Meta.

    Also extends ``inbox_chats.ai_paused_until`` by the configured pause window
    (Starter vs default from ``ops_runtime_config``) so AI does not immediately
    race the human.

    Idempotency:

    - Default: ``idempotency_key = agent:{chat_id}:{new_message_id}`` (retries that create a
      second message still get a new id — use the header for strict dedupe).
    - Optional header ``Idempotency-Key``: 1-128 chars ``[A-Za-z0-9_-]``. Same key + same user
      returns the existing message + outbox row without duplicating sends.
    """
    assert_role_in(user, (ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))
    scope = resolve_client_scope(user, explicit_client_id=client_id)
    if not _is_uuid(chat_id):
        raise HTTPException(status_code=400, detail="invalid chat_id")
    text_body = body.text.strip()
    if not text_body:
        raise HTTPException(status_code=400, detail="text is required")
    client_key = _parse_client_idempotency_key(idempotency_key_header)

    with engine.begin() as conn:
        chat = _load_chat(conn, chat_id, scope)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")

        # Agents may only reply on chats they own; owners + super_admin may reply on any.
        if user.role == ROLE_AGENT:
            current = _active_assignment(conn, chat_id)
            if not current or current["assigned_to_user_id"] != user.id:
                raise HTTPException(status_code=403, detail="agent is not assigned to this chat")

        if not chat.get("waba_number"):
            raise HTTPException(
                status_code=409,
                detail="chat has no associated wa_number (cannot enqueue outbox row)",
            )

        pause_h = _pause_hours_agent_reply(conn, scope)

        if client_key:
            idem = f"agent:{chat_id}:{user.id}:{client_key}"
            replay = conn.execute(
                text(
                    """
                    SELECT m.id::text, m.text, m.timestamp, o.id::text
                    FROM inbox_messages m
                    LEFT JOIN wa_outbox o ON o.idempotency_key = :idem
                    WHERE m.chat_id = CAST(:cid AS uuid)
                      AND m.sender = 'agent'
                      AND m.direction = 'out'
                      AND m.meta_payload->>'client_idempotency_key' = :ck
                    ORDER BY m.timestamp DESC
                    LIMIT 1
                    """
                ),
                {"idem": idem, "cid": chat_id, "ck": client_key},
            ).fetchone()
            if replay and replay[0]:
                msg_id, stored_text, msg_ts, outbox_id_opt = replay[0], replay[1], replay[2], replay[3]
                if outbox_id_opt:
                    msg_out = MessageOut(
                        id=msg_id,
                        chat_id=chat_id,
                        direction="out",
                        sender="agent",
                        text=stored_text,
                        timestamp=msg_ts,
                        meta_msg_id=None,
                        source="inbox_messages",
                    )
                    conn.execute(
                        text(
                            """
                            UPDATE inbox_chats
                            SET ai_paused_until = now() + make_interval(hours => :ph)
                            WHERE id = CAST(:cid AS uuid)
                            """
                        ),
                        {"cid": chat_id, "ph": pause_h},
                    )
                    return ReplyResponse(
                        message=msg_out,
                        outbox_id=str(outbox_id_opt),
                        idempotency_key=idem,
                    )
                outbox_id = conn.execute(
                    text(
                        """
                        INSERT INTO wa_outbox(
                          client_id, chat_id, to_phone_e164, from_wa_number_id,
                          kind, body_text, idempotency_key, status
                        )
                        VALUES (
                          CAST(:client AS uuid), CAST(:cid AS uuid), :to_phone, CAST(:from_id AS uuid),
                          'AGENT_REPLY', :body, :idem, 'PENDING'
                        )
                        ON CONFLICT (idempotency_key) DO UPDATE
                          SET body_text = EXCLUDED.body_text
                        RETURNING id::text
                        """
                    ),
                    {
                        "client": scope,
                        "cid": chat_id,
                        "to_phone": chat["customer_phone"],
                        "from_id": chat["waba_number"],
                        "body": text_body,
                        "idem": idem,
                    },
                ).scalar_one()
                conn.execute(
                    text(
                        """
                        UPDATE inbox_chats
                        SET last_outbound_at = now(),
                            state = 'AGENT_ACTIVE',
                            ai_paused_until = now() + make_interval(hours => :ph)
                        WHERE id = CAST(:cid AS uuid)
                        """
                    ),
                    {"cid": chat_id, "ph": pause_h},
                )
                msg_out = MessageOut(
                    id=msg_id,
                    chat_id=chat_id,
                    direction="out",
                    sender="agent",
                    text=text_body,
                    timestamp=msg_ts,
                    meta_msg_id=None,
                    source="inbox_messages",
                )
                hub.publish(
                    scope,
                    EVENT_MESSAGE_NEW,
                    {"chat_id": chat_id, "message": msg_out.model_dump(mode="json")},
                )
                if chat["state"] != "AGENT_ACTIVE":
                    _publish_state_change(scope, chat_id, chat["state"], "AGENT_ACTIVE")
                return ReplyResponse(message=msg_out, outbox_id=str(outbox_id), idempotency_key=idem)

        meta: dict[str, Any] = {"by_user_id": user.id, "by_role": user.role}
        if client_key:
            meta["client_idempotency_key"] = client_key

        msg_row = conn.execute(
            text(
                """
                INSERT INTO inbox_messages (chat_id, direction, sender, text, timestamp, meta_payload)
                VALUES (CAST(:cid AS uuid), 'out', 'agent', :body, now(), CAST(:meta AS jsonb))
                RETURNING id::text, timestamp
                """
            ),
            {
                "cid": chat_id,
                "body": text_body,
                "meta": json.dumps(meta),
            },
        ).fetchone()
        msg_id = msg_row[0]
        msg_ts = msg_row[1]
        idem = f"agent:{chat_id}:{user.id}:{client_key}" if client_key else f"agent:{chat_id}:{msg_id}"

        outbox_id = conn.execute(
            text(
                """
                INSERT INTO wa_outbox(
                  client_id, chat_id, to_phone_e164, from_wa_number_id,
                  kind, body_text, idempotency_key, status
                )
                VALUES (
                  CAST(:client AS uuid), CAST(:cid AS uuid), :to_phone, CAST(:from_id AS uuid),
                  'AGENT_REPLY', :body, :idem, 'PENDING'
                )
                ON CONFLICT (idempotency_key) DO UPDATE
                  SET body_text = EXCLUDED.body_text
                RETURNING id::text
                """
            ),
            {
                "client": scope,
                "cid": chat_id,
                "to_phone": chat["customer_phone"],
                "from_id": chat["waba_number"],
                "body": text_body,
                "idem": idem,
            },
        ).scalar_one()

        conn.execute(
            text(
                """
                UPDATE inbox_chats
                SET last_outbound_at = now(),
                    state = 'AGENT_ACTIVE',
                    ai_paused_until = now() + make_interval(hours => :ph)
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": chat_id, "ph": pause_h},
        )

    msg_out = MessageOut(
        id=msg_id,
        chat_id=chat_id,
        direction="out",
        sender="agent",
        text=text_body,
        timestamp=msg_ts,
        meta_msg_id=None,
        source="inbox_messages",
    )
    hub.publish(
        scope,
        EVENT_MESSAGE_NEW,
        {"chat_id": chat_id, "message": msg_out.model_dump(mode="json")},
    )
    if chat["state"] != "AGENT_ACTIVE":
        _publish_state_change(scope, chat_id, chat["state"], "AGENT_ACTIVE")
    return ReplyResponse(message=msg_out, outbox_id=str(outbox_id), idempotency_key=idem)
