from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.ops_api.routes_extended import router as extended_router


@pytest.fixture
def super_admin() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000099",
        client_id=None,
        role="super_admin",
        email="admin@example.com",
        name="Admin",
    )


def test_list_alerts(super_admin: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    conn.execute.return_value.all.return_value = [
        (
            "a1",
            "OUTBOX_DEAD_SPIKE",
            "warning",
            "dead spike",
            {"count": 3},
            datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
        )
    ]
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    eng = MagicMock()
    eng.begin.return_value = ctx
    monkeypatch.setattr("backend.apps.ops_api.routes_extended.engine", eng)

    app = FastAPI()
    app.include_router(extended_router)

    def _user() -> CurrentUser:
        return super_admin

    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as client:
        res = client.get("/ops/alerts", headers={"Authorization": "Bearer x"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["alert_type"] == "OUTBOX_DEAD_SPIKE"
