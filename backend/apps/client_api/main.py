from __future__ import annotations

"""ZY Smart Serv — client_api (M3/M4).

REST + WebSocket surface for owners / agents / super_admin to drive the inbox.

Run locally:
    $env:PYTHONPATH = "$PWD"
    $env:DATABASE_URL = "postgresql+psycopg://..."
    $env:CLIENT_API_JWT_SECRET = "use-a-strong-random-value"
    python -m uvicorn backend.apps.client_api.main:app --reload --port 8085
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from backend.shared.config import settings
from backend.shared.db import db_ping

from .events import hub, poller
from .routes_auth import router as auth_router
from .routes_dash import router as dash_router
from .routes_inbox import router as inbox_router
from .routes_ws import router as ws_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    poller.start()
    try:
        yield
    finally:
        await poller.stop()


app = FastAPI(
    title="ZY Smart Serv - client_api",
    version="0.1.0",
    description="Inbox, assignments, typing, WS, and read-only dashboard aggregates (owner/agent/super_admin).",
    lifespan=lifespan,
)


def _cors_origins() -> list[str]:
    raw = (settings.client_api_cors_origins or "").strip()
    if not raw:
        return ["*"]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/ready", response_class=PlainTextResponse)
def ready() -> str:
    try:
        db_ping()
        return "ok"
    except Exception:
        raise HTTPException(status_code=503, detail="db not ready")


@app.get("/_internal/ws/subscribers")
def ws_subscribers() -> dict[str, int]:
    """Diagnostic: total in-process WS subscriber count. Not auth-gated; safe in dev only."""
    if settings.app_env != "dev":
        raise HTTPException(status_code=404, detail="not found")
    return {"subscribers": hub.subscriber_count()}


app.include_router(auth_router)
app.include_router(inbox_router)
app.include_router(dash_router)
app.include_router(ws_router)
