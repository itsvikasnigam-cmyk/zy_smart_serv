from __future__ import annotations

from typing import Any

import httpx

from backend.shared.config import settings


def _paddle_api_base() -> str:
    env = (settings.billing_paddle_environment or "sandbox").strip().lower()
    if env in ("live", "production", "prod"):
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def paddle_create_transaction(*, payload: dict[str, Any]) -> dict[str, Any]:
    api_key = (settings.billing_paddle_api_key or "").strip()
    if not api_key:
        raise RuntimeError("Paddle API key not configured (BILLING_PADDLE_API_KEY)")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    ver = (settings.billing_paddle_api_version or "1").strip()
    if ver:
        headers["Paddle-Version"] = ver

    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{_paddle_api_base()}/transactions",
            json=payload,
            headers=headers,
        )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        return data["data"] if isinstance(data["data"], dict) else data
    return data if isinstance(data, dict) else {"raw": data}
