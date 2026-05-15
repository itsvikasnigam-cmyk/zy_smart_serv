from __future__ import annotations

"""ZY Smart Serv — ops_api (M9 SOP / Runbook Center).

Dedicated FastAPI app for super-admin SOP CRUD and run logs (keeps surface separate
from inbox ``client_api`` and webhooks).

Run locally:

```powershell
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://..."
$env:CLIENT_API_JWT_SECRET = "<same secret as client_api>"
python -m alembic -c backend\\alembic.ini upgrade head
python -m uvicorn backend.apps.ops_api.main:app --reload --port 8087
```

Auth: ``Authorization: Bearer <JWT>`` where the JWT is issued by ``client_api``
``POST /auth/login`` for a user with role ``super_admin`` only.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from backend.shared.config import settings
from backend.shared.db import db_ping

from .routes_extended import router as ops_extended_router
from .routes_ops import router as ops_router


def _cors_origins() -> list[str]:
    raw = (settings.ops_api_cors_origins or "").strip()
    if not raw:
        return ["*"]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="ZY Smart Serv - ops_api",
    version="0.1.0",
    description="M9 SOP library + versioned Markdown + run logs (super_admin JWT from client_api).",
)

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


app.include_router(ops_router)
app.include_router(ops_extended_router)
