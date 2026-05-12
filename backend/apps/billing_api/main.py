from __future__ import annotations

"""ZY Smart Serv — billing_api (M5).

Dedicated FastAPI app for payment-provider webhooks (keeps signing + raw-body
verification isolated from WA gateway and client_api).

Run locally:

```powershell
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://..."
$env:BILLING_RAZORPAY_WEBHOOK_SECRET = "<from Razorpay Dashboard>"
$env:BILLING_PADDLE_WEBHOOK_SECRET = "<from Paddle notification destination>"
python -m uvicorn backend.apps.billing_api.main:app --reload --port 8086
```

Webhook URLs (default local base ``http://127.0.0.1:8086``):

- ``POST /webhooks/razorpay``
- ``POST /webhooks/paddle``
"""

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.apps.billing_api.process_webhook import process_paddle_webhook, process_razorpay_webhook
from backend.apps.billing_api.verify_signatures import verify_paddle_signature, verify_razorpay_signature
from backend.shared.config import settings
from backend.shared.db import db_ping, engine

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZY Smart Serv - billing_api",
    version="0.1.0",
    description="Razorpay and Paddle webhooks; maps to api_clients + bill_* tables.",
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
        raise HTTPException(status_code=503, detail="db not ready")


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
    except Exception:
        logger.exception("razorpay webhook processing error")
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
    except Exception:
        logger.exception("paddle webhook processing error")
        raise HTTPException(status_code=500, detail="webhook processing failed") from None

    return JSONResponse(out, status_code=200)
