"""ops_api (M9): OpenAPI paths + super_admin-only RBAC."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.client_api.deps import CurrentUser, get_current_user
from backend.apps.ops_api.routes_ops import router as ops_router


def _minimal_ops_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ops_router)
    return app


def test_ops_paths_registered_in_openapi() -> None:
    app = _minimal_ops_app()
    paths = app.openapi()["paths"]
    assert "/ops/sops" in paths
    assert "/ops/sops/{sop_id}" in paths
    assert "/ops/sops/{sop_id}/versions" in paths
    assert "/ops/sops/{sop_id}/run" in paths
    assert "/ops/runs" in paths
    assert "/ops/runs/{run_id}" in paths


def test_ops_routes_forbidden_for_owner() -> None:
    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000001",
        client_id="00000000-0000-4000-8000-000000000002",
        role="owner",
        email=None,
        name=None,
    )
    try:
        with TestClient(app) as client:
            assert client.get("/ops/sops").status_code == 403
            assert client.post("/ops/sops", json={}).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_ops_routes_forbidden_for_agent() -> None:
    app = _minimal_ops_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000003",
        client_id="00000000-0000-4000-8000-000000000002",
        role="agent",
        email=None,
        name=None,
    )
    try:
        with TestClient(app) as client:
            assert client.get("/ops/runs").status_code == 403
    finally:
        app.dependency_overrides.clear()
