"""Dashboard routes (Chat J): OpenAPI registration + RBAC-only checks.

These tests **do not** execute handler SQL or response assembly. For that, see
``tests/test_dash_handlers_mocked_db.py`` (mocks ``engine.begin()`` and runs
the real route code end-to-end for JSON responses).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.client_api.routes_dash import router as dash_router


def _minimal_dash_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dash_router)
    return app


def test_dash_paths_registered_in_openapi() -> None:
    app = _minimal_dash_app()
    schema = app.openapi()
    paths = schema["paths"]
    assert "/dash/client/overview" in paths
    assert "/dash/client/agents" in paths
    assert "/dash/client/quality" in paths
    assert "/dash/admin/overview" in paths
    assert "/dash/admin/collections" in paths
    assert "/dash/admin/providers/razorpay" in paths
    assert "/dash/admin/providers/paddle" in paths
    assert "/dash/admin/ops/whatsapp" in paths
    assert "/dash/admin/geo" in paths
    assert "/dash/admin/admin/geo" in paths


def test_admin_routes_forbidden_for_owner() -> None:
    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        client_id="00000000-0000-0000-0000-000000000002",
        role="owner",
        email=None,
        name=None,
    )
    try:
        with TestClient(app) as client:
            r = client.get("/dash/admin/overview")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_super_admin_client_overview_requires_client_id() -> None:
    app = _minimal_dash_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-0000-0000-000000000099",
        client_id=None,
        role="super_admin",
        email=None,
        name=None,
    )
    try:
        with TestClient(app) as client:
            r = client.get("/dash/client/overview")
            assert r.status_code == 400
            assert "client_id" in r.json().get("detail", "").lower()
    finally:
        app.dependency_overrides.clear()
