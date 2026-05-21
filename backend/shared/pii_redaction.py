"""Chat V: redact phone, email, and card-like patterns before telemetry/misfire storage."""

from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
# 10–15 digit runs (E.164 / local) — applied after card pass to avoid double hits.
_PHONE_DIGITS_RE = re.compile(r"\b\d{10,15}\b")
# 13–19 digits with optional separators (PAN/card-like).
_CARD_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")


def redact_pii_text(text: str | None) -> str | None:
    if not text:
        return text
    out = _CARD_RE.sub("[CARD]", text)
    out = _EMAIL_RE.sub("[EMAIL]", out)
    out = _PHONE_DIGITS_RE.sub("[PHONE]", out)
    return out


def redact_pii_json(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii_text(value)
    if isinstance(value, dict):
        return {k: redact_pii_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_pii_json(v) for v in value]
    return value
