"""Chat V: privacy / compliance ops_runtime_config loader."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)

PRIVACY_POLICY_KEY = "privacy.policy"
BLOCKLIST_MODE_KEY = "privacy.blocklist_mode"
BLOCKLIST_REPLY_KEY = "privacy.blocklist_customer_reply"
TELEMETRY_RETENTION_KEY = "privacy.telemetry_retention_days"

BlocklistMode = Literal["drop", "handoff"]

_DEFAULT_POLICY = {
    "blocklist_mode": "handoff",
    "blocklist_customer_reply": (
        "Thanks for your message. We are unable to process automated replies for this number. "
        "A team member will follow up if needed."
    ),
    "telemetry_retention_days": 30,
    "redaction_enabled": True,
}


@dataclass(frozen=True)
class PrivacyPolicy:
    blocklist_mode: BlocklistMode
    blocklist_customer_reply: str | None
    telemetry_retention_days: int
    redaction_enabled: bool


def merge_privacy_policy(value_json: Any | None) -> dict[str, Any]:
    out = dict(_DEFAULT_POLICY)
    if isinstance(value_json, dict):
        for key, val in value_json.items():
            if key in out and val is not None:
                out[key] = val
    return out


def _coerce_blocklist_mode(raw: Any) -> BlocklistMode:
    s = str(raw or "handoff").strip().lower()
    return "drop" if s == "drop" else "handoff"


def _coerce_retention_days(raw: Any) -> int:
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 30
    return max(1, min(days, 3650))


def policy_from_merged(merged: dict[str, Any]) -> PrivacyPolicy:
    reply = merged.get("blocklist_customer_reply")
    reply_s = str(reply).strip() if isinstance(reply, str) and reply.strip() else None
    return PrivacyPolicy(
        blocklist_mode=_coerce_blocklist_mode(merged.get("blocklist_mode")),
        blocklist_customer_reply=reply_s,
        telemetry_retention_days=_coerce_retention_days(merged.get("telemetry_retention_days")),
        redaction_enabled=bool(merged.get("redaction_enabled", True)),
    )


def load_privacy_policy_conn(conn: Connection) -> PrivacyPolicy:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
        {"k": PRIVACY_POLICY_KEY},
    ).fetchone()
    merged = merge_privacy_policy(row[0] if row else None)
    return policy_from_merged(merged)


def load_privacy_policy_engine(engine: Engine) -> PrivacyPolicy:
    try:
        with engine.connect() as conn:
            return load_privacy_policy_conn(conn)
    except Exception:
        logger.exception("privacy.policy read failed; using defaults")
        return policy_from_merged(_DEFAULT_POLICY)


def load_blocklist_customer_reply_conn(conn: Connection) -> str | None:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
        {"k": BLOCKLIST_REPLY_KEY},
    ).fetchone()
    if row and isinstance(row[0], str) and row[0].strip():
        return row[0].strip()
    policy = load_privacy_policy_conn(conn)
    return policy.blocklist_customer_reply
