from __future__ import annotations

from typing import Any

import httpx

from backend.shared.config import settings


def razorpay_create_order(
    *,
    amount_paise: int,
    currency: str,
    receipt: str,
    notes: dict[str, str],
) -> dict[str, Any]:
    key_id = (settings.billing_razorpay_key_id or "").strip()
    key_secret = (settings.billing_razorpay_key_secret or "").strip()
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay API keys not configured (BILLING_RAZORPAY_KEY_ID / BILLING_RAZORPAY_KEY_SECRET)")

    body: dict[str, Any] = {
        "amount": amount_paise,
        "currency": currency.upper(),
        "receipt": receipt[:40],
        "notes": notes,
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.post(
            "https://api.razorpay.com/v1/orders",
            json=body,
            auth=(key_id, key_secret),
        )
    r.raise_for_status()
    return r.json()
