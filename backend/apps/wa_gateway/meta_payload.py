from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


def normalize_customer_phone_for_route(phone: str) -> str:
    """
    Canonical key for wa_trial_map / inbox matching against Meta `from` values.
    Meta sends E.164 without '+'; keep digits only so ' +91 9.. ' and '919..' match.
    """
    return "".join(ch for ch in phone.strip() if ch.isdigit())


def coerce_string_list_json(value: Any) -> list[str]:
    """Normalize ops_runtime_config JSONB list / JSON string into non-empty substrings."""
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return coerce_string_list_json(parsed)
        except json.JSONDecodeError:
            return [value.strip()]
    return []


def inbound_matches_urgent_substrings(text: str, substrings: list[str]) -> bool:
    """Gateway U1: case-insensitive substring match (aligns with ai_engine key ``ai.urgent_bypass_substrings``)."""
    if not text or not substrings:
        return False
    lower = text.lower()
    return any(s.lower() in lower for s in substrings if s)


@dataclass(frozen=True)
class InboundMessage:
    meta_msg_id: str
    from_phone: str
    to_phone_number_id: str | None
    timestamp: int | None
    text: str
    raw: dict[str, Any]
    message_type: str
    text_like: bool
    media_metadata: dict[str, Any]


def _media_metadata(msg: dict[str, Any], msg_type: str) -> dict[str, Any]:
    data = msg.get(msg_type)
    if not isinstance(data, dict):
        return {"type": msg_type}
    keys = ("id", "mime_type", "sha256", "filename", "caption")
    out = {k: data.get(k) for k in keys if data.get(k) is not None}
    out["type"] = msg_type
    return out


def _interactive_text(msg: dict[str, Any]) -> str | None:
    data = msg.get("interactive")
    if not isinstance(data, dict):
        return None
    i_type = str(data.get("type") or "").strip()
    if i_type == "button_reply":
        reply = data.get("button_reply") or {}
        if isinstance(reply, dict):
            title = str(reply.get("title") or "").strip()
            return f"[button] {title}" if title else None
    if i_type == "list_reply":
        reply = data.get("list_reply") or {}
        if isinstance(reply, dict):
            title = str(reply.get("title") or "").strip()
            desc = str(reply.get("description") or "").strip()
            if title and desc:
                return f"[list] {title} - {desc}"
            return f"[list] {title}" if title else None
    return None


def extract_inbound_messages(payload: dict[str, Any]) -> list[InboundMessage]:
    """
    Extract inbound customer messages from Meta WhatsApp Cloud API webhook payload.
    Handles common cases; stores raw payload for forward compatibility.
    """
    out: list[InboundMessage] = []

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            to_phone_number_id = metadata.get("phone_number_id")

            for msg in value.get("messages", []) or []:
                meta_msg_id = msg.get("id")
                from_phone = msg.get("from")
                if not meta_msg_id or not from_phone:
                    continue

                msg_type = str(msg.get("type") or "unknown")
                text = ""
                text_like = False
                media_meta: dict[str, Any] = {}
                if msg_type == "text":
                    text = ((msg.get("text") or {}).get("body")) or ""
                    text_like = True
                elif msg_type == "button":
                    text = str((msg.get("button") or {}).get("text") or "[button]").strip()
                    text_like = True
                elif msg_type == "interactive":
                    text = _interactive_text(msg) or "[interactive]"
                    text_like = text != "[interactive]"
                else:
                    # Store useful metadata, but do not pass media to the text LLM path yet.
                    text = f"[{msg_type}]"
                    media_meta = _media_metadata(msg, msg_type)

                ts_raw = msg.get("timestamp")
                ts: int | None = None
                if ts_raw is not None:
                    try:
                        ts = int(ts_raw)
                    except (TypeError, ValueError):
                        ts = None

                out.append(
                    InboundMessage(
                        meta_msg_id=str(meta_msg_id),
                        from_phone=str(from_phone),
                        to_phone_number_id=str(to_phone_number_id) if to_phone_number_id else None,
                        timestamp=ts,
                        text=text,
                        raw=msg,
                        message_type=msg_type,
                        text_like=text_like,
                        media_metadata=media_meta,
                    )
                )

    return out

