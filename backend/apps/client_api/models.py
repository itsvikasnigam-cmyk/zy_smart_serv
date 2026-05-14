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


# --- Dashboard (M8 / Chat J): read-only aggregates for Flutter G/H ---


class DashMessageTotals(BaseModel):
    """Rolled-up message counts (metrics_daily_client when present, else zeros)."""

    customer: int = 0
    ai: int = 0
    agent: int = 0
    system: int = 0


class DashUsageToday(BaseModel):
    """UTC calendar day row from ``bill_usage_daily`` (zeros if worker has not written yet)."""

    usage_date: str | None = None
    inbound_customer_messages: int = 0
    outbound_ai_messages: int = 0
    outbound_agent_messages: int = 0
    outbound_system_messages: int = 0
    soft_threshold_crossed_at: datetime | None = None
    hard_threshold_crossed_at: datetime | None = None


class DashClientOverviewOut(BaseModel):
    client_id: str
    business_name: str | None
    entitlement_plan: str | None
    billing_provider: str | None
    trial_end: datetime | None
    wa_numbers_count: int = 0
    chats_by_state: dict[str, int] = Field(default_factory=dict)
    usage_today: DashUsageToday
    messages_last_7d: DashMessageTotals = Field(default_factory=DashMessageTotals)
    placeholder: dict[str, Any] = Field(
        default_factory=dict,
        description="Reserved keys for future quality/SLA fields; phase-1 stubs stay empty.",
    )


class DashAgentRow(BaseModel):
    user_id: str
    name: str | None
    email: str | None
    replies_last_7d: int = 0
    active_assigned_chats: int = 0


class DashClientAgentsOut(BaseModel):
    client_id: str
    agents: list[DashAgentRow] = Field(default_factory=list)


class DashClientQualityOut(BaseModel):
    client_id: str
    chats_pending_agent: int = 0
    chats_with_handoff_reason_7d: int = 0
    median_first_response_seconds: float | None = None
    csat_placeholder: float | None = None
    messages_last_7d: DashMessageTotals = Field(default_factory=DashMessageTotals)
    notes: str = (
        "Phase-1: handoff/pending counts from inbox_chats; latency/CSAT placeholders until "
        "instrumentation lands."
    )


class DashAdminOverviewOut(BaseModel):
    total_clients: int = 0
    clients_by_entitlement: dict[str, int] = Field(default_factory=dict)
    total_chats: int = 0
    total_wa_numbers: int = 0
    outbox_by_status: dict[str, int] = Field(default_factory=dict)
    hourly_system_last_24h: DashMessageTotals = Field(default_factory=DashMessageTotals)
    hourly_outbox_dead_last_48h: int = 0
    hourly_outbox_created_last_48h: int = 0
    placeholder: dict[str, Any] = Field(default_factory=dict)


class DashAdminCollectionsOut(BaseModel):
    """Phase-1 billing aggregates; MRR-style fields stubbed until invoices land."""

    active_subscriptions: int = 0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    estimated_mrr_minor_units: int = 0
    notes: str = "estimated_mrr_minor_units is a stub (0) until pricing + invoice APIs exist."


class DashAdminProviderOut(BaseModel):
    provider: Literal["razorpay", "paddle"]
    subscriptions_by_status: dict[str, int] = Field(default_factory=dict)
    events_last_7d: int = 0
    plans_configured: int = 0


class DashAdminOpsWhatsappOut(BaseModel):
    wa_numbers_by_type: dict[str, int] = Field(default_factory=dict)
    outbox_by_status: dict[str, int] = Field(default_factory=dict)
    outbox_by_kind: dict[str, int] = Field(default_factory=dict)


class DashAdminGeoRow(BaseModel):
    country_code: str
    wa_numbers: int


class DashAdminGeoOut(BaseModel):
    rows: list[DashAdminGeoRow] = Field(default_factory=list)
    notes: str = "Country from wa_numbers.country_code; unknown bucket when null."
