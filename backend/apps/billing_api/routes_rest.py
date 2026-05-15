from __future__ import annotations

import json
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.apps.billing_api.providers.paddle_client import paddle_create_transaction
from backend.apps.billing_api.providers.razorpay_client import razorpay_create_order
from backend.apps.client_api.auth import ROLE_OWNER, ROLE_SUPER_ADMIN
from backend.apps.client_api.deps import CurrentUser, get_current_user, require_roles, resolve_client_scope
from backend.shared.config import settings
from backend.shared.db import engine

router = APIRouter(prefix="/billing", tags=["billing"])


class RazorpayCheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_paise: int = Field(..., ge=100, description="Amount in minor units (paise)")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str | None = Field(default=None, max_length=40)
    notes: dict[str, str] = Field(default_factory=dict)


class PaddleCheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Paddle Billing items, e.g. [{'price_id': 'pri_...', 'quantity': 1}]",
    )
    custom_data: dict[str, str] = Field(default_factory=dict)


class KycIndiaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any]


@router.post("/razorpay/create-checkout")
def billing_razorpay_create_checkout(
    checkout: RazorpayCheckoutIn,
    user: CurrentUser = Depends(require_roles(ROLE_OWNER, ROLE_SUPER_ADMIN)),
    client_id: str | None = Query(default=None, description="Required for super_admin"),
) -> dict[str, Any]:
    cid = resolve_client_scope(user, explicit_client_id=client_id)
    notes = dict(checkout.notes)
    notes.setdefault("client_id", cid)
    receipt = checkout.receipt or f"zy_{cid[:8]}_{secrets.token_hex(4)}"
    try:
        order = razorpay_create_order(
            amount_paise=checkout.amount_paise,
            currency=checkout.currency,
            receipt=receipt,
            notes=notes,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"razorpay_error: {e}",
        ) from e

    return {
        "provider": "razorpay",
        "key_id": settings.billing_razorpay_key_id,
        "order": order,
    }


@router.post("/paddle/create-checkout")
def billing_paddle_create_checkout(
    checkout: PaddleCheckoutIn,
    user: CurrentUser = Depends(require_roles(ROLE_OWNER, ROLE_SUPER_ADMIN)),
    client_id: str | None = Query(default=None),
) -> dict[str, Any]:
    cid = resolve_client_scope(user, explicit_client_id=client_id)
    custom = dict(checkout.custom_data)
    custom.setdefault("client_id", cid)
    payload: dict[str, Any] = {"items": checkout.items, "custom_data": custom}
    try:
        data = paddle_create_transaction(payload=payload)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"paddle_error: {e}") from e

    return {"provider": "paddle", "transaction": data}


@router.get("/subscription")
def billing_get_subscription(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = Query(default=None),
) -> dict[str, Any]:
    cid = resolve_client_scope(user, explicit_client_id=client_id)
    with engine.connect() as conn:
        crow = conn.execute(
            text(
                """
                SELECT entitlement_plan::text, billing_provider::text, billing_plan_code::text,
                       trial_end
                FROM api_clients
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": cid},
        ).fetchone()
        if not crow:
            raise HTTPException(status_code=404, detail="client not found")
        sub = conn.execute(
            text(
                """
                SELECT provider::text, external_subscription_id::text, status::text,
                       plan_code::text, current_period_end, updated_at
                FROM bill_subscriptions
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"cid": cid},
        ).fetchone()

    out: dict[str, Any] = {
        "client_id": cid,
        "entitlement_plan": crow[0],
        "billing_provider": crow[1],
        "billing_plan_code": crow[2],
        "trial_end": crow[3].isoformat() if crow[3] is not None else None,
        "subscription": None,
    }
    if sub:
        out["subscription"] = {
            "provider": sub[0],
            "external_subscription_id": sub[1],
            "status": sub[2],
            "plan_code": sub[3],
            "current_period_end": sub[4].isoformat() if sub[4] is not None else None,
            "updated_at": sub[5].isoformat() if sub[5] is not None else None,
        }
    return out


@router.get("/invoices")
def billing_get_invoices(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    cid = resolve_client_scope(user, explicit_client_id=client_id)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT provider::text, external_invoice_id::text, amount_minor, currency::text,
                       status::text, issued_at, created_at
                FROM bill_invoices
                WHERE client_id = CAST(:cid AS uuid)
                ORDER BY COALESCE(issued_at, created_at) DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"cid": cid, "lim": limit},
        ).all()
    invoices = [
        {
            "provider": r[0],
            "external_invoice_id": r[1],
            "amount_minor": r[2],
            "currency": r[3],
            "status": r[4],
            "issued_at": r[5].isoformat() if r[5] is not None else None,
            "created_at": r[6].isoformat() if r[6] is not None else None,
        }
        for r in rows
    ]
    return {"client_id": cid, "invoices": invoices}


@router.post("/kyc/india")
def billing_kyc_india_submit(
    submission: KycIndiaIn,
    user: CurrentUser = Depends(require_roles(ROLE_OWNER, ROLE_SUPER_ADMIN)),
    client_id: str | None = Query(default=None),
) -> dict[str, bool]:
    """Persist India KYC payload. Returns HTTP 200 with JSON body ``{"ok": true}`` (avoids FastAPI 204 empty-body registration issues)."""
    cid = resolve_client_scope(user, explicit_client_id=client_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE api_clients
                SET kyc_india_json = CAST(:payload AS jsonb),
                    kyc_submitted_at = now(),
                    kyc_status = CASE
                      WHEN kyc_status IS NULL OR TRIM(kyc_status) = '' THEN 'submitted'
                      ELSE kyc_status
                    END
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"payload": json.dumps(submission.data), "cid": cid},
        )
    return {"ok": True}


class KycReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(verified|rejected)$")
    reason: str | None = Field(default=None, max_length=500)


@router.post("/kyc/india/{client_id}/review")
def billing_kyc_india_review(
    client_id: str,
    body: KycReviewIn,
    user: CurrentUser = Depends(require_roles(ROLE_SUPER_ADMIN)),
) -> dict[str, Any]:
    """Super-admin: mark India KYC verified or rejected."""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT 1 FROM api_clients WHERE id = CAST(:cid AS uuid)"),
            {"cid": client_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="client not found")
        conn.execute(
            text(
                """
                UPDATE api_clients
                SET kyc_status = :st,
                    kyc_verified_at = CASE WHEN :st = 'verified' THEN now() ELSE kyc_verified_at END
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": client_id, "st": body.status},
        )
    return {"ok": True, "client_id": client_id, "kyc_status": body.status, "reviewed_by": user.id}
