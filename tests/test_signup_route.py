"""Signup route shape (no Postgres)."""

from __future__ import annotations

from backend.apps.client_api.routes_signup import SignupIn, SignupOut


def test_signup_models() -> None:
    body = SignupIn(
        email="newbiz@example.com",
        password="Secret!2026",
        business_name="New Biz",
        trial_days=7,
    )
    assert body.trial_days == 7
    out = SignupOut(
        client_id="c",
        owner_user_id="u",
        email=body.email,
        entitlement_plan="trial",
        trial_end="2026-01-01T00:00:00+00:00",
        message="ok",
    )
    assert out.entitlement_plan == "trial"
