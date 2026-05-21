"""Exercise ``routes_dash`` handler bodies (SQL → Pydantic) with a mocked DB connection.

RBAC still uses real ``resolve_client_scope`` / ``require_roles`` via FastAPI dependencies;
only ``engine.begin()`` / ``conn.execute()`` are faked so CI does not require Postgres.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.client_api.routes_dash import router as dash_router


class _ExecResult:
    """Minimal stand-in for ``CursorResult`` (only methods used by ``routes_dash``)."""

    def __init__(
        self,
        *,
        fetchone: tuple | None = None,
        all_rows: list[tuple] | None = None,
        scalar_one: object | None = None,
    ) -> None:
        self._fetchone = fetchone
        self._all = all_rows
        self._scalar = scalar_one

    def fetchone(self) -> tuple | None:
        return self._fetchone

    def all(self) -> list[tuple]:
        return self._all if self._all is not None else []

    def scalar_one(self) -> object:
        assert self._scalar is not None
        return self._scalar


class _FakeConn:
    def __init__(self, queue: list[_ExecResult]) -> None:
        self._queue = queue

    def execute(self, stmt: object, params: object | None = None) -> _ExecResult:  # noqa: ARG002
        if not self._queue:
            raise AssertionError("conn.execute called more times than test queued for")
        return self._queue.pop(0)


class _FakeBegin:
    def __init__(self, queue: list[_ExecResult]) -> None:
        self._queue = queue

    def __enter__(self) -> _FakeConn:
        return _FakeConn(self._queue)

    def __exit__(self, *args: object) -> None:
        return None


def _minimal_dash_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dash_router)
    return app


def _assert_queue_drained(queue: list[_ExecResult]) -> None:
    assert not queue, f"unused queued results remain: {len(queue)}"


@pytest.fixture
def owner_user() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        client_id="00000000-0000-0000-0000-0000000000aa",
        role="owner",
        email="o@example.com",
        name="Owner",
    )


@pytest.fixture
def super_admin() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-0000-0000-000000000099",
        client_id=None,
        role="super_admin",
        email="admin@example.com",
        name="Admin",
    )


def test_dash_client_overview_handler_assembles_response(
    monkeypatch: pytest.MonkeyPatch, owner_user: CurrentUser
) -> None:
    cid = owner_user.client_id
    assert cid is not None
    queue: list[_ExecResult] = [
        _ExecResult(fetchone=("Acme", "trial", "razorpay", None)),
        _ExecResult(all_rows=[("AI_ACTIVE", 3), ("HUMAN_REQ", 1)]),
        _ExecResult(scalar_one=2),
        _ExecResult(fetchone=(date(2026, 5, 13), 10, 4, 1, 0, None, None)),
        _ExecResult(fetchone=(100, 20, 5, 2)),
    ]

    class _Eng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(queue)

    monkeypatch.setattr("backend.apps.client_api.routes_dash.engine", _Eng())

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: owner_user
    try:
        with TestClient(app) as client:
            r = client.get("/dash/client/overview")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["client_id"] == cid
            assert body["business_name"] == "Acme"
            assert body["chats_by_state"] == {"AI_ACTIVE": 3, "HUMAN_REQ": 1}
            assert body["wa_numbers_count"] == 2
            assert body["usage_today"]["inbound_customer_messages"] == 10
            assert body["messages_last_7d"]["customer"] == 100
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_client_overview_404_when_client_row_missing(
    monkeypatch: pytest.MonkeyPatch, owner_user: CurrentUser
) -> None:
    queue: list[_ExecResult] = [_ExecResult(fetchone=None)]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: owner_user
    try:
        with TestClient(app) as client:
            assert client.get("/dash/client/overview").status_code == 404
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_client_agents_handler(
    monkeypatch: pytest.MonkeyPatch, owner_user: CurrentUser
) -> None:
    cid = owner_user.client_id
    agent_id = "00000000-0000-0000-0000-0000000000bb"
    queue: list[_ExecResult] = [
        _ExecResult(all_rows=[(agent_id, 2)]),
        _ExecResult(all_rows=[(agent_id, "Pat", "pat@ex.com", 7)]),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: owner_user
    try:
        with TestClient(app) as client:
            r = client.get("/dash/client/agents")
            assert r.status_code == 200, r.text
            agents = r.json()["agents"]
            assert len(agents) == 1
            assert agents[0]["user_id"] == agent_id
            assert agents[0]["replies_last_7d"] == 7
            assert agents[0]["active_assigned_chats"] == 2
            assert r.json()["client_id"] == cid
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_client_quality_handler(
    monkeypatch: pytest.MonkeyPatch, owner_user: CurrentUser
) -> None:
    cid = owner_user.client_id
    queue: list[_ExecResult] = [
        _ExecResult(scalar_one=4),
        _ExecResult(scalar_one=1),
        _ExecResult(fetchone=(50, 10, 3, 1)),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: owner_user
    try:
        with TestClient(app) as client:
            r = client.get("/dash/client/quality")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["client_id"] == cid
            assert b["chats_pending_agent"] == 4
            assert b["chats_with_handoff_reason_7d"] == 1
            assert b["messages_last_7d"]["customer"] == 50
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_super_admin_client_overview_with_query_param(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    tenant = "11111111-1111-1111-1111-111111111111"
    queue: list[_ExecResult] = [
        _ExecResult(fetchone=("Co", "growth", "paddle", None)),
        _ExecResult(all_rows=[]),
        _ExecResult(scalar_one=0),
        _ExecResult(fetchone=None),
        _ExecResult(fetchone=None),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/client/overview", params={"client_id": tenant})
            assert r.status_code == 200, r.text
            assert r.json()["client_id"] == tenant
            assert r.json()["entitlement_plan"] == "growth"
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_overview_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(scalar_one=10),
        _ExecResult(all_rows=[("trial", 6), ("starter", 4)]),
        _ExecResult(scalar_one=200),
        _ExecResult(scalar_one=8),
        _ExecResult(all_rows=[("PENDING", 3), ("DEAD", 2)]),
        _ExecResult(fetchone=(1, 2, 3, 0, 0)),
        _ExecResult(fetchone=(5, 9)),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/overview")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["total_clients"] == 10
            assert b["clients_by_entitlement"] == {"trial": 6, "starter": 4}
            assert b["total_chats"] == 200
            assert b["outbox_by_status"] == {"PENDING": 3, "DEAD": 2}
            assert b["hourly_system_last_24h"]["customer"] == 1
            assert b["hourly_outbox_dead_last_48h"] == 5
            assert b["hourly_outbox_created_last_48h"] == 9
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_collections_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(
            all_rows=[
                ("razorpay", "active", 2),
                ("razorpay", "cancelled", 1),
                ("paddle", "paid", 3),
            ]
        ),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/collections")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["by_provider"] == {"razorpay": 3, "paddle": 3}
            assert b["active_subscriptions"] == 5  # active + paid + paid counts 2+3 for active_like
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_cost_margin_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(
            all_rows=[
                (
                    "17682c77-1524-4ebd-94e5-958e7f37ac60",
                    "ZY Test",
                    "starter",
                    10,
                    1.5,
                    33.3,
                    31.8,
                )
            ]
        ),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/cost-margin")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["period_days"] == 30
            assert b["rows"][0]["business_name"] == "ZY Test"
            assert b["totals"]["estimated_margin_inr"] == 31.8
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_provider_razorpay_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(all_rows=[("active", 2), ("trial", 1)]),
        _ExecResult(scalar_one=42),
        _ExecResult(scalar_one=3),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/providers/razorpay")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["provider"] == "razorpay"
            assert b["subscriptions_by_status"] == {"active": 2, "trial": 1}
            assert b["events_last_7d"] == 42
            assert b["plans_configured"] == 3
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_ops_whatsapp_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(all_rows=[("PROD", 4), ("TRIAL", 1)]),
        _ExecResult(all_rows=[("PENDING", 10), ("SENT", 2)]),
        _ExecResult(all_rows=[("AI_REPLY", 5), ("AGENT_REPLY", 1)]),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/ops/whatsapp")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["wa_numbers_by_type"] == {"PROD": 4, "TRIAL": 1}
            assert b["outbox_by_status"]["PENDING"] == 10
            assert b["outbox_by_kind"]["AI_REPLY"] == 5
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_dash_admin_geo_handler(
    monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser
) -> None:
    queue: list[_ExecResult] = [
        _ExecResult(all_rows=[("IN", 3), ("unknown", 1)]),
    ]
    monkeypatch.setattr(
        "backend.apps.client_api.routes_dash.engine",
        type("_E", (), {"begin": lambda self: _FakeBegin(queue)})(),
    )

    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/geo")
            assert r.status_code == 200, r.text
            rows = r.json()["rows"]
            assert {x["country_code"]: x["wa_numbers"] for x in rows} == {"IN": 3, "unknown": 1}
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)
