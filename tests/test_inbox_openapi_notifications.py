"""Inbox notification routes: OpenAPI registration (no DB)."""

from __future__ import annotations

from fastapi import FastAPI

from backend.apps.client_api.routes_inbox import router as inbox_router


def _minimal_inbox_app() -> FastAPI:
    app = FastAPI()
    app.include_router(inbox_router)
    return app


def test_notification_paths_registered_in_openapi() -> None:
    app = _minimal_inbox_app()
    schema = app.openapi()
    paths = schema["paths"]
    assert "/inbox/notifications" in paths
    assert "/inbox/notifications/{notification_id}/read" in paths
