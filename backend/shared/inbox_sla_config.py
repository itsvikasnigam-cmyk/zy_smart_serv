"""Owner-wait + agent SLA knobs (Option C phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.product_config import _coerce_positive_int, load_ops_json

OWNER_WAIT_KEY = "inbox.owner_wait"
SLA_AGENT_MINUTES_KEY = "inbox.sla.agent_response_minutes"

DEFAULT_REALERT_HOURS = 4
DEFAULT_APOLOGY_HOURS = 8
DEFAULT_APOLOGY_REPLY = (
    "We are sorry for the delay. Our team is still working on your request "
    "and will get back to you as soon as possible. Thank you for your patience."
)
DEFAULT_AGENT_SLA_MINUTES = 30


@dataclass(frozen=True)
class OwnerWaitConfig:
    realert_hours: int
    apology_hours: int
    apology_customer_reply: str


@dataclass(frozen=True)
class AgentSlaConfig:
    response_minutes: int


def load_owner_wait_config(conn: Connection) -> OwnerWaitConfig:
    raw = load_ops_json(conn, OWNER_WAIT_KEY)
    d: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return OwnerWaitConfig(
        realert_hours=_coerce_positive_int(d.get("realert_hours"), DEFAULT_REALERT_HOURS),
        apology_hours=_coerce_positive_int(d.get("apology_hours"), DEFAULT_APOLOGY_HOURS),
        apology_customer_reply=str(d.get("apology_customer_reply") or DEFAULT_APOLOGY_REPLY).strip()
        or DEFAULT_APOLOGY_REPLY,
    )


def load_agent_sla_config(conn: Connection) -> AgentSlaConfig:
    raw = load_ops_json(conn, SLA_AGENT_MINUTES_KEY)
    minutes = _coerce_positive_int(raw, DEFAULT_AGENT_SLA_MINUTES)
    return AgentSlaConfig(response_minutes=minutes)


def reset_inbox_sla_markers(
    conn: Connection,
    chat_id: str,
    *,
    clear_owner_wait: bool = True,
    clear_sla_breach: bool = True,
) -> None:
    sets: list[str] = []
    if clear_owner_wait:
        sets.extend(["owner_wait_4h_at = NULL", "owner_wait_8h_at = NULL"])
    if clear_sla_breach:
        sets.append("sla_breach_at = NULL")
    if not sets:
        return
    conn.execute(
        text(
            f"""
            UPDATE inbox_chats
            SET {', '.join(sets)}
            WHERE id = CAST(:cid AS uuid)
            """
        ),
        {"cid": chat_id},
    )
