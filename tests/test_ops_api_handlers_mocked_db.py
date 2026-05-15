"""Exercise ``ops_api`` handler SQL paths with a mocked DB (no Postgres in CI)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.ops_api.routes_ops import router as ops_router


class _ExecResult:
    def __init__(
        self,
        *,
        fetchone: tuple | None = None,
        all_rows: list[tuple] | None = None,
    ) -> None:
        self._fetchone = fetchone
        self._all = all_rows

    def fetchone(self) -> tuple | None:
        return self._fetchone

    def all(self) -> list[tuple]:
        return self._all if self._all is not None else []


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


def _minimal_ops_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ops_router)
    return app


def _assert_queue_drained(queue: list[_ExecResult]) -> None:
    assert not queue, f"unused queued results remain: {len(queue)}"


@pytest.fixture
def super_admin() -> CurrentUser:
    return CurrentUser(
        id="00000000-0000-4000-8000-000000000099",
        client_id=None,
        role="super_admin",
        email="admin@example.com",
        name="Admin",
    )


def test_create_sop_then_get_detail(monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser) -> None:
    sid = "11111111-1111-4111-8111-111111111111"
    ts = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    queue: list[_ExecResult] = [
        _ExecResult(fetchone=(sid, 1)),
        _ExecResult(),
        _ExecResult(
            fetchone=(
                sid,
                "On-call",
                "on-call",
                "ops",
                "active",
                1,
                ts,
                ts,
                "# Steps\n1. Check",
            )
        ),
    ]

    class _Eng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(queue)

    monkeypatch.setattr("backend.apps.ops_api.routes_ops.engine", _Eng())

    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            c = client.post(
                "/ops/sops",
                json={
                    "title": "On-call",
                    "slug": "on-call",
                    "category": "ops",
                    "status": "active",
                    "body_markdown": "# Steps\n1. Check",
                },
            )
            assert c.status_code == 201, c.text
            assert c.json() == {"id": sid, "current_version": 1}

            g = client.get(f"/ops/sops/{sid}")
            assert g.status_code == 200, g.text
            body = g.json()
            assert body["slug"] == "on-call"
            assert body["current_version"] == 1
            assert "Check" in body["body_markdown"]
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_put_sop_bumps_version(monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser) -> None:
    sid = "22222222-2222-4222-8222-222222222222"
    queue: list[_ExecResult] = [
        _ExecResult(fetchone=(1,)),
        _ExecResult(),
        _ExecResult(),
    ]

    class _Eng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(queue)

    monkeypatch.setattr("backend.apps.ops_api.routes_ops.engine", _Eng())

    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.put(
                f"/ops/sops/{sid}",
                json={
                    "title": "On-call v2",
                    "category": "ops",
                    "status": "archived",
                    "body_markdown": "updated",
                },
            )
            assert r.status_code == 200, r.text
            assert r.json() == {"id": sid, "current_version": 2}
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_start_run_returns_id(monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser) -> None:
    sid = "33333333-3333-4333-8333-333333333333"
    rid = "44444444-4444-4444-8444-444444444444"
    queue: list[_ExecResult] = [
        _ExecResult(fetchone=(2,)),
        _ExecResult(fetchone=(rid,)),
    ]

    class _Eng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(queue)

    monkeypatch.setattr("backend.apps.ops_api.routes_ops.engine", _Eng())

    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            r = client.post(
                f"/ops/sops/{sid}/run",
                json={"context_json": {"note": "trial"}, "trigger_type": "manual"},
            )
            assert r.status_code == 201, r.text
            assert r.json() == {"id": rid, "sop_id": sid, "sop_version_at_run": 2}
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(queue)


def test_list_runs_and_get_run(monkeypatch: pytest.MonkeyPatch, super_admin: CurrentUser) -> None:
    ts = datetime(2026, 5, 13, 15, 30, 0, tzinfo=timezone.utc)
    row = (
        "44444444-4444-4444-8444-444444444444",
        "33333333-3333-4333-8333-333333333333",
        2,
        {"k": "v"},
        "manual",
        "00000000-0000-4000-8000-000000000099",
        None,
        ts,
    )
    list_queue: list[_ExecResult] = [_ExecResult(all_rows=[row])]
    get_queue: list[_ExecResult] = [_ExecResult(fetchone=row)]

    class _ListEng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(list_queue)

    class _GetEng:
        def begin(self) -> _FakeBegin:
            return _FakeBegin(get_queue)

    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        with TestClient(app) as client:
            monkeypatch.setattr("backend.apps.ops_api.routes_ops.engine", _ListEng())
            lr = client.get("/ops/runs")
            assert lr.status_code == 200
            data = lr.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == row[0]
            assert data["items"][0]["context_json"] == {"k": "v"}

            monkeypatch.setattr("backend.apps.ops_api.routes_ops.engine", _GetEng())
            gr = client.get(f"/ops/runs/{row[0]}")
            assert gr.status_code == 200
            assert gr.json()["sop_version_at_run"] == 2
    finally:
        app.dependency_overrides.clear()

    _assert_queue_drained(list_queue)
    _assert_queue_drained(get_queue)
