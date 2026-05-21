"""WhatsApp customer service window (24h) policy and outbound send resolution."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.shared.broadcast_gating import build_template_outbox_body

POLICY_KEY = "wa.service_window.policy"

DEFAULT_POLICY: dict[str, Any] = {
    "window_hours": 24,
    "session_kinds": ["AI_REPLY", "AGENT_REPLY", "PAYWALL", "OWNER_ALERT"],
    "use_last_customer_msg_fallback": True,
    "fallback_templates": {},
}


class ServiceWindowExpiredError(Exception):
    """Session message outside window and no configured template fallback."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def merge_service_window_policy(value_json: Any | None) -> dict[str, Any]:
    merged = dict(DEFAULT_POLICY)
    if isinstance(value_json, dict):
        for k, v in value_json.items():
            merged[k] = v
    kinds = merged.get("session_kinds")
    if isinstance(kinds, list):
        merged["session_kinds"] = [str(x).strip().upper() for x in kinds if str(x).strip()]
    return merged


def parse_meta_expiration_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def window_expires_after_customer_message(
    *,
    at: datetime | None = None,
    window_hours: float | int = 24,
) -> datetime:
    base = at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    else:
        base = base.astimezone(timezone.utc)
    hours = float(window_hours)
    return base + timedelta(hours=hours)


def is_session_window_open(
    *,
    expires_at: datetime | None,
    last_customer_msg_at: datetime | None,
    policy: dict[str, Any],
    now: datetime | None = None,
) -> bool:
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    if expires_at is not None:
        exp = expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        else:
            exp = exp.astimezone(timezone.utc)
        if exp > now_utc:
            return True

    if not policy.get("use_last_customer_msg_fallback", True):
        return False
    if last_customer_msg_at is None:
        return False

    hours = float(policy.get("window_hours") or 24)
    return window_expires_after_customer_message(at=last_customer_msg_at, window_hours=hours) > now_utc


def pick_fallback_template(kind: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    fb = policy.get("fallback_templates") or {}
    if not isinstance(fb, dict):
        return None
    k = (kind or "").strip().upper()
    spec = fb.get(k) or fb.get("default")
    if isinstance(spec, dict) and spec.get("template_name") and spec.get("language"):
        return spec
    return None


def resolve_session_outbound(
    *,
    kind: str,
    body_text: str,
    window_open: bool,
    policy: dict[str, Any],
) -> tuple[str, str]:
    """
    Returns (send_mode, body) where send_mode is ``text`` or ``template``.
    ``TEMPLATE`` kind always passes through as template body JSON.
    """
    k = (kind or "").strip().upper()
    if k == "TEMPLATE":
        return "template", body_text

    session_kinds = {str(x).strip().upper() for x in (policy.get("session_kinds") or [])}
    if k not in session_kinds:
        return "text", body_text

    if window_open:
        return "text", body_text

    spec = pick_fallback_template(k, policy)
    if not spec:
        raise ServiceWindowExpiredError(
            f"service_window_expired: kind={k} and no fallback_templates[{k}] or default in {POLICY_KEY}"
        )

    components = spec.get("components")
    if components is not None and not isinstance(components, list):
        components = []
    body = build_template_outbox_body(
        template_name=str(spec["template_name"]),
        language=str(spec["language"]),
        components=components,
    )
    return "template", body


def conversation_expiration_from_raw(raw: dict[str, Any]) -> datetime | None:
    conv = raw.get("conversation")
    if not isinstance(conv, dict):
        return None
    return parse_meta_expiration_timestamp(conv.get("expiration_timestamp"))
