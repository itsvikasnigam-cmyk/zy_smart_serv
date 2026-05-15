"""
Meta WhatsApp Cloud API **status** webhook parsing.

`meta_status` in the gateway resolves `client_id` from `wa_outbox` using `meta_message_id`;
this module stays free of SQL parameter casting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class StatusEvent:
    meta_message_id: str
    event_type: Literal["SENT", "DELIVERED", "READ", "FAILED"]
    raw: dict[str, Any]


def extract_status_events(payload: dict[str, Any]) -> list[StatusEvent]:
    out: list[StatusEvent] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for st in value.get("statuses", []) or []:
                msg_id = st.get("id")
                if not msg_id:
                    continue
                status = (st.get("status") or "").lower()
                mapped: str | None = None
                if status in ("sent",):
                    mapped = "SENT"
                elif status in ("delivered",):
                    mapped = "DELIVERED"
                elif status in ("read",):
                    mapped = "READ"
                elif status in ("failed",):
                    mapped = "FAILED"
                if not mapped:
                    continue
                out.append(StatusEvent(meta_message_id=str(msg_id), event_type=mapped, raw=st))
    return out


def extract_meta_errors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Meta ``messages`` / system ``errors`` payloads (optional ``POST /webhooks/meta/errors`` sink).
    Returns raw error dicts for append-only storage.
    """
    out: list[dict[str, Any]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for err in value.get("errors", []) or []:
                if isinstance(err, dict):
                    out.append(err)
    return out

