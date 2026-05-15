from __future__ import annotations

from fastapi.testclient import TestClient

from backend.apps.billing_api.main import app


def test_billing_subscription_requires_bearer() -> None:
    client = TestClient(app)
    r = client.get("/billing/subscription")
    assert r.status_code == 401


def test_billing_kyc_requires_bearer() -> None:
    client = TestClient(app)
    r = client.post("/billing/kyc/india", json={"data": {"pan": "XXXXX0000X"}})
    assert r.status_code == 401
