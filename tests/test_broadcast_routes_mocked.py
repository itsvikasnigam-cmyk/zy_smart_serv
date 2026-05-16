from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.client_api.routes_broadcast import router as broadcast_router


@pytest.fixture
def super_admin() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000099",
        client_id=None,
        role="super_admin",
        email="admin@example.com",
        name="Admin",
    )


def _app(user: CurrentUser) -> FastAPI:
    app = FastAPI()
    app.include_router(broadcast_router)

    def _user() -> CurrentUser:
        return user

    app.dependency_overrides[get_current_user] = _user
    return app


def test_put_opt_in_requires_client_id(super_admin: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    eng = MagicMock()
    monkeypatch.setattr("backend.apps.client_api.routes_broadcast.engine", eng)
    with TestClient(_app(super_admin)) as client:
        res = client.put(
            "/broadcast/opt-in",
            json={"customer_phone_e164": "+919876543210", "opted_in": True},
        )
    assert res.status_code == 400


def test_list_opt_in_scoped(super_admin: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    conn.execute.return_value.all.return_value = [
        (
            "17682c77-1524-4ebd-94e5-958e7f37ac60",
            "+919876543210",
            True,
            "flutter",
            datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    ]
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    eng = MagicMock()
    eng.begin.return_value = ctx
    monkeypatch.setattr("backend.apps.client_api.routes_broadcast.engine", eng)

    cid = "17682c77-1524-4ebd-94e5-958e7f37ac60"
    with TestClient(_app(super_admin)) as client:
        res = client.get("/broadcast/opt-in", params={"client_id": cid})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["opted_in"] is True
