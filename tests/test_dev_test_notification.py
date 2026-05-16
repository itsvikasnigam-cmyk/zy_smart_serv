from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.client_api.routes_inbox import router as inbox_router


@pytest.fixture
def owner() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        client_id="17682c77-1524-4ebd-94e5-958e7f37ac60",
        role="owner",
        email="owner1@example.com",
        name="Owner",
    )


def test_dev_test_notification_dev_only(owner: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.apps.client_api.routes_inbox.settings.app_env", "dev")

    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        ("chat-uuid",),
        ("notif-uuid", "2026-05-15"),
    ]
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    eng = MagicMock()
    eng.begin.return_value = ctx
    monkeypatch.setattr("backend.apps.client_api.routes_inbox.engine", eng)
    monkeypatch.setattr(
        "backend.apps.client_api.routes_inbox.insert_notification",
        lambda *a, **k: ("notif-uuid", None),
    )

    app = FastAPI()
    app.include_router(inbox_router)

    def _user() -> CurrentUser:
        return owner

    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client:
        res = client.post("/inbox/notifications/dev-test")
    assert res.status_code == 200
    assert res.json()["id"] == "notif-uuid"


def test_dev_test_notification_hidden_in_prod(owner: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.apps.client_api.routes_inbox.settings.app_env", "prod")
    app = FastAPI()
    app.include_router(inbox_router)

    def _user() -> CurrentUser:
        return owner

    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client:
        res = client.post("/inbox/notifications/dev-test")
    assert res.status_code == 404
