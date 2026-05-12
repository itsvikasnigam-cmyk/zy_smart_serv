"""
Live HTTP roundtrip against a running WA gateway (optional).

Default CI / local: skipped — no Docker or Postgres required.

Manual / staging verification:
  1. Apply migrations and seed `wa_numbers` for your Meta phone_number_id.
  2. Start gateway: `python -m uvicorn backend.apps.wa_gateway.main:app --port 8081`
  3. PowerShell:
       $env:RUN_WA_GATEWAY_E2E="1"
       $env:ZY_E2E_META_PHONE_NUMBER_ID="<numeric id from dev_seed>"
       python -m pytest tests/test_gateway_e2e_optional.py -v

Automated Postgres in Docker (testcontainers) is not wired yet; use the steps above
or extend this module when `testcontainers` is added to requirements.
"""

from __future__ import annotations

import os

import httpx
import pytest

from backend.tools.dev_send_inbound import build_meta_inbound_webhook_payload


@pytest.mark.skipif(
    os.environ.get("RUN_WA_GATEWAY_E2E") != "1",
    reason="Set RUN_WA_GATEWAY_E2E=1 to POST against a live local gateway (see module docstring).",
)
def test_live_gateway_inbound_accepts_dev_payload() -> None:
    base = os.environ.get("ZY_E2E_GATEWAY_URL", "http://127.0.0.1:8081").rstrip("/")
    phone_id = os.environ.get("ZY_E2E_META_PHONE_NUMBER_ID", "").strip()
    if not phone_id:
        pytest.skip("ZY_E2E_META_PHONE_NUMBER_ID must be set for live gateway e2e.")

    payload = build_meta_inbound_webhook_payload(
        meta_phone_number_id=phone_id,
        from_phone="+919876543210",
        text_body="e2e optional pytest",
    )
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{base}/webhooks/meta/inbound", json=payload)

    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("stored", 0) >= 1
