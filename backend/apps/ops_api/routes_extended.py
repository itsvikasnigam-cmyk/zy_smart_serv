from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.shared.db import engine

from .deps import SuperAdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops-extended"])


class AlertEventOut(BaseModel):
    id: str
    alert_type: str
    severity: str
    summary: str
    detail_json: dict[str, Any]
    created_at: datetime


class AlertListOut(BaseModel):
    items: list[AlertEventOut]
    next_cursor: str | None = None


class RuntimeConfigOut(BaseModel):
    key: str
    value_json: Any
    updated_at: datetime | None = None


class RuntimeConfigPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_json: Any
    reason: str | None = Field(default=None, max_length=500)


@router.get("/runtime-config/{key:path}", response_model=RuntimeConfigOut)
def get_runtime_config(_user: SuperAdminUser, key: str) -> RuntimeConfigOut:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT key, value_json, updated_at
                FROM ops_runtime_config WHERE key = :k LIMIT 1
                """
            ),
            {"k": key},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="config key not found")
    return RuntimeConfigOut(key=row[0], value_json=row[1], updated_at=row[2])


@router.put("/runtime-config/{key:path}", response_model=RuntimeConfigOut)
def put_runtime_config(user: SuperAdminUser, key: str, body: RuntimeConfigPut) -> RuntimeConfigOut:
    uid = user.id
    with engine.begin() as conn:
        old = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k FOR UPDATE"),
            {"k": key},
        ).fetchone()
        if old:
            conn.execute(
                text(
                    """
                    INSERT INTO ops_runtime_config_audit (
                      key, old_value_json, new_value_json, changed_by_user_id, reason
                    )
                    VALUES (
                      :k, CAST(:old AS jsonb), CAST(:new AS jsonb), CAST(:uid AS uuid), :reason
                    )
                    """
                ),
                {
                    "k": key,
                    "old": json.dumps(old[0]) if old[0] is not None else None,
                    "new": json.dumps(body.value_json),
                    "uid": uid,
                    "reason": body.reason,
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE ops_runtime_config
                    SET value_json = CAST(:new AS jsonb),
                        updated_by_user_id = CAST(:uid AS uuid),
                        updated_at = now()
                    WHERE key = :k
                    """
                ),
                {"k": key, "new": json.dumps(body.value_json), "uid": uid},
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO ops_runtime_config (key, value_json, updated_by_user_id)
                    VALUES (:k, CAST(:new AS jsonb), CAST(:uid AS uuid))
                    """
                ),
                {"k": key, "new": json.dumps(body.value_json), "uid": uid},
            )
        row = conn.execute(
            text("SELECT key, value_json, updated_at FROM ops_runtime_config WHERE key = :k"),
            {"k": key},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="config upsert failed")
    return RuntimeConfigOut(key=row[0], value_json=row[1], updated_at=row[2])


@router.get("/alerts", response_model=AlertListOut)
def list_alert_events(
    _user: SuperAdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
    alert_type: Annotated[str | None, Query()] = None,
) -> AlertListOut:
    """Recent ``ops_alert_events`` for super-admin dashboard (M7 surfacing)."""
    params: dict[str, Any] = {"lim": limit + 1}
    parts = [
        """
        SELECT id::text, alert_type, severity, summary, detail_json, created_at
        FROM ops_alert_events
        WHERE 1=1
        """
    ]
    if alert_type:
        parts.append("AND alert_type = :atype")
        params["atype"] = alert_type.strip()
    if cursor:
        parts.append("AND created_at < CAST(:cur AS timestamptz)")
        params["cur"] = cursor
    parts.append("ORDER BY created_at DESC LIMIT :lim")
    with engine.begin() as conn:
        rows = conn.execute(text("\n".join(parts)), params).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    items = [
        AlertEventOut(
            id=r[0],
            alert_type=r[1],
            severity=r[2],
            summary=r[3],
            detail_json=r[4] if isinstance(r[4], dict) else {},
            created_at=r[5],
        )
        for r in page
    ]
    next_cursor = page[-1][5].isoformat() if has_more and page else None
    return AlertListOut(items=items, next_cursor=next_cursor)
