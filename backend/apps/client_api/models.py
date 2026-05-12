from __future__ import annotations

"""Pydantic request/response schemas for client_api.

Conventions:
- IDs are emitted as strings (uuid4 stringified) for stable JSON.
- Timestamps are ISO-8601 strings (datetime objects serialize that way by default).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ChatState = Literal["AI_ACTIVE", "PENDING_AGENT", "AGENT_ACTIVE", "RESOLVED"]
LEGAL_CHAT_STATES: tuple[str, ...] = ("AI_ACTIVE", "PENDING_AGENT", "AGENT_ACTIVE", "RESOLVED")

Role = Literal["owner", "agent", "super_admin"]


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_Forbid):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    client_id: str | None
    name: str | None
    email: str | None
    role: Role


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    user: UserOut


class MessageOut(BaseModel):
    id: str
    chat_id: str
    direction: Literal["in", "out"]
    sender: Literal["ai", "agent", "customer", "system"]
    text: str
    timestamp: datetime
    meta_msg_id: str | None = None
    source: Literal["inbox_messages", "wa_outbox"] = "inbox_messages"
    outbox_status: str | None = None
    outbox_kind: str | None = None


class AssignmentOut(BaseModel):
    id: str
    chat_id: str
    assigned_to_user_id: str
    assigned_by_user_id: str | None
    reason: str | None
    note: str | None
    status: Literal["ACTIVE", "REASSIGNED", "RESOLVED"]
    created_at: datetime
    ended_at: datetime | None


class ChatListItem(BaseModel):
    id: str
    client_id: str
    customer_phone: str
    state: str
    assigned_agent_id: str | None
    last_customer_msg_at: datetime | None
    last_outbound_at: datetime | None
    created_at: datetime
    last_message_preview: str | None = None


class ChatList(BaseModel):
    items: list[ChatListItem]
    next_cursor: str | None = None


class ChatDetail(BaseModel):
    chat: ChatListItem
    assignment: AssignmentOut | None
    messages: list[MessageOut]
    pending_outbound: list[MessageOut] = Field(default_factory=list)


class AssignRequest(_Forbid):
    user_id: str
    reason: str | None = None
    note: str | None = None


class UnassignRequest(_Forbid):
    reason: str | None = None


class EscalateRequest(_Forbid):
    to_user_id: str | None = None
    reason: str | None = None


class TypingRequest(_Forbid):
    state: Literal["typing", "stopped"] = "typing"
    ttl_seconds: int = Field(default=5, ge=1, le=30)


class ReplyRequest(_Forbid):
    text: str = Field(min_length=1, max_length=4096)


class ReplyResponse(BaseModel):
    message: MessageOut
    outbox_id: str
    idempotency_key: str


class WSEnvelope(BaseModel):
    """Outbound envelope shape published over the websocket. Clients should
    discriminate on ``event`` and consume ``data`` accordingly."""

    event: Literal[
        "message_new",
        "assignment_changed",
        "typing",
        "chat_state_changed",
        "hello",
        "error",
    ]
    data: dict[str, Any]
    ts: datetime
