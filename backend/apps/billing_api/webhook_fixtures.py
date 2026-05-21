"""Synthetic Razorpay/Paddle webhook payloads for dev simulation (Chat R)."""

from __future__ import annotations

import time
import uuid
from typing import Any


def razorpay_subscription_activated(
    *,
    client_id: str,
    subscription_id: str | None = None,
    plan_id: str = "plan_dev_starter",
    entitlement_plan: str = "starter",
    event_id: str | None = None,
) -> dict[str, Any]:
    sub_id = subscription_id or f"sub_dev_{uuid.uuid4().hex[:12]}"
    eid = event_id or f"evt_rz_{uuid.uuid4().hex[:12]}"
    return {
        "entity": "event",
        "account_id": "acc_dev",
        "event": "subscription.activated",
        "contains": ["subscription"],
        "payload": {
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "entity": "subscription",
                    "plan_id": plan_id,
                    "status": "active",
                    "current_end": int(time.time()) + 86400 * 30,
                    "notes": {
                        "client_id": client_id,
                        "entitlement_plan": entitlement_plan,
                    },
                }
            }
        },
        "created_at": int(time.time()),
        "id": eid,
    }


def razorpay_subscription_cancelled(
    *,
    client_id: str,
    subscription_id: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    eid = event_id or f"evt_rz_{uuid.uuid4().hex[:12]}"
    return {
        "entity": "event",
        "event": "subscription.cancelled",
        "payload": {
            "subscription": {
                "entity": {
                    "id": subscription_id,
                    "status": "cancelled",
                    "notes": {"client_id": client_id},
                }
            }
        },
        "id": eid,
    }


def paddle_subscription_activated(
    *,
    client_id: str,
    subscription_id: str | None = None,
    price_id: str = "pri_dev_starter",
    entitlement_plan: str = "starter",
    event_id: str | None = None,
) -> dict[str, Any]:
    sub_id = subscription_id or f"sub_pdl_{uuid.uuid4().hex[:12]}"
    eid = event_id or f"evt_pdl_{uuid.uuid4().hex[:12]}"
    return {
        "event_id": eid,
        "event_type": "subscription.activated",
        "data": {
            "id": sub_id,
            "status": "active",
            "custom_data": {
                "client_id": client_id,
                "entitlement_plan": entitlement_plan,
            },
            "items": [{"price": {"id": price_id}}],
            "current_billing_period": {
                "ends_at": "2030-01-01T00:00:00Z",
            },
        },
    }


def paddle_subscription_canceled(
    *,
    client_id: str,
    subscription_id: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    eid = event_id or f"evt_pdl_{uuid.uuid4().hex[:12]}"
    return {
        "event_id": eid,
        "event_type": "subscription.canceled",
        "data": {
            "id": subscription_id,
            "status": "canceled",
            "custom_data": {"client_id": client_id},
        },
    }
