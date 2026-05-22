"""Chat R: billing_api webhook HTTP contract (signatures, no DB required for 401 paths)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.apps.billing_api.main import app
from backend.apps.billing_api.verify_signatures import build_razorpay_signature


def test_razorpay_webhook_rejects_bad_signature() -> None:
    client = TestClient(app)
    body = b'{"id":"evt_x","event":"subscription.activated"}'
    with patch("backend.apps.billing_api.main.settings") as st:
        st.billing_razorpay_webhook_secret = "secret_test"
        r = client.post(
            "/webhooks/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": "bad"},
        )
    assert r.status_code == 401


def test_razorpay_webhook_503_when_secret_missing() -> None:
    client = TestClient(app)
    with patch("backend.apps.billing_api.main.settings") as st:
        st.billing_razorpay_webhook_secret = ""
        r = client.post("/webhooks/razorpay", content=b"{}")
    assert r.status_code == 503


def test_razorpay_webhook_accepts_valid_signature_mock_process() -> None:
    client = TestClient(app)
    secret = "secret_test"
    payload = {"id": "evt_ok", "event": "subscription.activated", "payload": {}}
    body = json.dumps(payload).encode("utf-8")
    sig = build_razorpay_signature(body, secret)
    mock_txn = MagicMock()
    mock_txn.__enter__.return_value = MagicMock()
    mock_txn.__exit__.return_value = False
    with patch("backend.apps.billing_api.main.settings") as st:
        st.billing_razorpay_webhook_secret = secret
        with (
            patch("backend.apps.billing_api.main.engine.begin", return_value=mock_txn),
            patch(
                "backend.apps.billing_api.main.process_razorpay_webhook",
                return_value={"status": "accepted"},
            ),
        ):
            r = client.post(
                "/webhooks/razorpay",
                content=body,
                headers={"X-Razorpay-Signature": sig},
            )
    assert r.status_code == 200
    assert r.json().get("status") == "accepted"
