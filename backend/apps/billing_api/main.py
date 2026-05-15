from __future__ import annotations

"""ZY Smart Serv — billing_api (M5).

Dedicated FastAPI app for payment providers: **signed webhooks** (raw body) and
**REST** checkout / subscription reads / India KYC (JWT from ``client_api`` login).

Run locally:

```powershell
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://..."
$env:CLIENT_API_JWT_SECRET = "<same as client_api>"
$env:BILLING_RAZORPAY_WEBHOOK_SECRET = "<from Razorpay Dashboard>"
$env:BILLING_PADDLE_WEBHOOK_SECRET = "<from Paddle notification destination>"
# For POST /billing/*/create-checkout (server-to-provider API calls):
$env:BILLING_RAZORPAY_KEY_ID = "..."
$env:BILLING_RAZORPAY_KEY_SECRET = "..."
$env:BILLING_PADDLE_API_KEY = "..."
python -m uvicorn backend.apps.billing_api.main:app --reload --port 8086
```

**Webhooks** (no auth; signature only):

- ``POST /webhooks/razorpay``
- ``POST /webhooks/paddle``

**REST** (``Authorization: Bearer`` JWT from ``client_api`` ``/auth/login``):

- ``POST /billing/razorpay/create-checkout``
- ``POST /billing/paddle/create-checkout``
- ``GET /billing/subscription``
- ``GET /billing/invoices``
- ``POST /billing/kyc/india`` — JSON ``{"data":{...}}`` → ``200`` + ``{"ok": true}``

**Coordinate:** ``GET /dash/*`` (Chat **J**) is read-only analytics; **source of truth** for
entitlements and subscription rows is **this app + Postgres** (``api_clients``,
``bill_subscriptions``, ``bill_invoices``, ``bill_events``).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from backend.apps.billing_api.process_webhook import process_paddle_webhook, process_razorpay_webhook
from backend.apps.billing_api.routes_rest import router as billing_rest_router
from backend.apps.billing_api.verify_signatures import verify_paddle_signature, verify_razorpay_signature
from backend.shared.config import settings
from backend.shared.db import db_ping, engine
from backend.shared.ops_alerts import record_alert_event_safe

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZY Smart Serv - billing_api",
    version="0.2.0",
    description="Razorpay and Paddle webhooks + billing REST; maps to api_clients + bill_* tables.",
)


def _cors_origins() -> list[str]:
    raw = (settings.billing_api_cors_origins or "").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(billing_rest_router)


def _record_billing_webhook_failure(provider: str, exc: BaseException) -> None:
    """M7: persist + alert (no paging yet) when signed webhooks fail after verification."""
    detail = f"{type(exc).__name__}: {exc}"[:8000]
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO bill_webhook_processing_errors (provider, detail)
                    VALUES (:p, :d)
                    """
                ),
                {"p": provider, "d": detail},
            )
    except Exception:
        logger.exception("bill_webhook_processing_errors insert failed")
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    record_alert_event_safe(
        engine,
        alert_type="BILLING_WEBHOOK_PROCESSING_ERROR",
        severity="error",
        summary=f"{provider} webhook processing raised",
        detail={"provider": provider, "error": detail[:2000]},
        dedupe_key=f"billing_webhook_err:{provider}:{bucket}",
    )


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/ready", response_class=PlainTextResponse)
def ready() -> str:
    try:
        db_ping()
        return "ok"
    except Exception:
        raise HTTPException(status_code=503, detail="db not ready") from None


@app.post("/webhooks/razorpay")
async def webhooks_razorpay(request: Request) -> dict[str, Any]:
    secret = (settings.billing_razorpay_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="BILLING_RAZORPAY_WEBHOOK_SECRET not configured")

    body = await request.body()
    sig = request.headers.get("x-razorpay-signature")
    if not verify_razorpay_signature(body, sig, secret):
        raise HTTPException(status_code=401, detail="invalid razorpay signature")

    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e

    try:
        with engine.begin() as conn:
            out = process_razorpay_webhook(conn, payload)
    except Exception as e:
        logger.exception("razorpay webhook processing error")
        _record_billing_webhook_failure("razorpay", e)
        raise HTTPException(status_code=500, detail="webhook processing failed") from None

    return JSONResponse(out, status_code=200)


@app.post("/webhooks/paddle")
async def webhooks_paddle(request: Request) -> dict[str, Any]:
    secret = (settings.billing_paddle_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="BILLING_PADDLE_WEBHOOK_SECRET not configured")

    body = await request.body()
    sig = request.headers.get("paddle-signature")
    if not verify_paddle_signature(body, sig, secret):
        raise HTTPException(status_code=401, detail="invalid paddle signature")

    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail="invalid json body") from e

    try:
        with engine.begin() as conn:
            out = process_paddle_webhook(conn, payload)
    except Exception as e:
        logger.exception("paddle webhook processing error")
        _record_billing_webhook_failure("paddle", e)
        raise HTTPException(status_code=500, detail="webhook processing failed") from None

    return JSONResponse(out, status_code=200)
