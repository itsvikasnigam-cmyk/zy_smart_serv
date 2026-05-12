from __future__ import annotations

import hashlib
import hmac
from typing import Any


def verify_razorpay_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Razorpay: ``X-Razorpay-Signature`` is hex-encoded HMAC-SHA256 of the raw POST body
    using the webhook secret from the Razorpay Dashboard.
    """
    if not secret or signature_header is None:
        return False
    expected = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), signature_header.strip().lower())


def verify_paddle_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Paddle Billing: ``Paddle-Signature`` header format ``ts=<unix>;h1=<hex>`` where ``h1`` is
    HMAC-SHA256 of ``<ts>:<raw_body>`` (UTF-8) using the notification destination secret.
    """
    if not secret or not signature_header:
        return False
    parts: dict[str, str] = {}
    for piece in signature_header.split(";"):
        piece = piece.strip()
        if "=" in piece:
            k, v = piece.split("=", 1)
            parts[k.strip()] = v.strip()
    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False
    signed = f"{ts}:".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), msg=signed, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), h1.lower())


def razorpay_event_id(payload: dict[str, Any]) -> str | None:
    eid = payload.get("id")
    if isinstance(eid, str) and eid.strip():
        return eid.strip()
    return None


def razorpay_event_name(payload: dict[str, Any]) -> str:
    ev = payload.get("event")
    return ev if isinstance(ev, str) else "unknown"


def paddle_event_id(payload: dict[str, Any]) -> str | None:
    eid = payload.get("event_id")
    if isinstance(eid, str) and eid.strip():
        return eid.strip()
    return None


def paddle_event_type(payload: dict[str, Any]) -> str:
    et = payload.get("event_type")
    return et if isinstance(et, str) else "unknown"
