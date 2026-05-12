from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def normalize_customer_phone_for_route(phone: str) -> str:
    """
    Canonical key for wa_trial_map / inbox matching against Meta `from` values.
    Meta sends E.164 without '+'; keep digits only so ' +91 9.. ' and '919..' match.
    """
    return "".join(ch for ch in phone.strip() if ch.isdigit())


@dataclass(frozen=True)
class InboundMessage:
    meta_msg_id: str
    from_phone: str
    to_phone_number_id: str | None
    timestamp: int | None
    text: str
    raw: dict[str, Any]


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

                msg_type = msg.get("type")
                text = ""
                if msg_type == "text":
                    text = ((msg.get("text") or {}).get("body")) or ""
                else:
                    # We will implement media fetch + STT later. For now, capture the type.
                    text = f"[{msg_type or 'unknown'}]"

                out.append(
                    InboundMessage(
                        meta_msg_id=str(meta_msg_id),
                        from_phone=str(from_phone),
                        to_phone_number_id=str(to_phone_number_id) if to_phone_number_id else None,
                        timestamp=int(msg.get("timestamp")) if msg.get("timestamp") else None,
                        text=text,
                        raw=msg,
                    )
                )

    return out

