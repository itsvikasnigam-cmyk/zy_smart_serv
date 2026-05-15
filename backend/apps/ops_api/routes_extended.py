from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.shared.db import engine

from .deps import SuperAdminUser
from .models import RunOut

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


class ReleaseRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: str = Field(min_length=1, max_length=200)
    git_sha: str | None = Field(default=None, max_length=64)
    artifact_hash: str | None = Field(default=None, max_length=128)
    test_report_hash: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=4000)


class ReleaseOut(BaseModel):
    id: str
    build_id: str
    git_sha: str | None
    artifact_hash: str | None
    test_report_hash: str | None
    status: str
    notes: str | None
    promoted_at: datetime | None
    created_at: datetime


@router.get("/alerts", response_model=AlertListOut)
def list_alerts(
    _user: SuperAdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(description="Opaque created_at|id cursor")] = None,
    alert_type: Annotated[str | None, Query()] = None,
) -> AlertListOut:
    params: dict[str, object] = {"lim": limit + 1}
    parts = [
        """
        SELECT id::text, alert_type, severity, summary, detail_json, created_at
        FROM ops_alert_events
        WHERE 1=1
        """
    ]
    if alert_type:
        parts.append("AND alert_type = :atype")
        params["atype"] = alert_type
    if cursor:
        try:
            ts_s, cid = cursor.split("|", 1)
            params["c_ts"] = datetime.fromisoformat(ts_s.replace("Z", "+00:00"))
            params["c_id"] = cid
            parts.append(
                """
                AND (created_at, id) < (:c_ts, CAST(:c_id AS uuid))
                """
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail="invalid cursor") from e
    parts.append("ORDER BY created_at DESC, id DESC")
    parts.append("LIMIT :lim")
    sql = "\n".join(parts)
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    items: list[AlertEventOut] = []
    for r in page:
        detail = r[4] if isinstance(r[4], dict) else {}
        items.append(
            AlertEventOut(
                id=r[0],
                alert_type=r[1],
                severity=r[2],
                summary=r[3],
                detail_json=detail,
                created_at=r[5],
            )
        )
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = f"{last[5].isoformat()}|{last[0]}"
    return AlertListOut(items=items, next_cursor=next_cursor)


@router.get("/runtime-config/{key}", response_model=RuntimeConfigOut)
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


@router.put("/runtime-config/{key}", response_model=RuntimeConfigOut)
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
                    INSERT INTO ops_runtime_config_audit (key, old_value_json, new_value_json, changed_by_user_id, reason)
                    VALUES (:k, CAST(:old AS jsonb), CAST(:new AS jsonb), CAST(:uid AS uuid), :reason)
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


@router.get("/releases", response_model=list[ReleaseOut])
def list_releases(
    _user: SuperAdminUser,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ReleaseOut]:
    parts = [
        """
        SELECT id::text, build_id, git_sha, artifact_hash, test_report_hash,
               status, notes, promoted_at, created_at
        FROM ops_releases WHERE 1=1
        """
    ]
    params: dict[str, object] = {"lim": limit}
    if status_filter:
        parts.append("AND status = :st")
        params["st"] = status_filter
    parts.append("ORDER BY created_at DESC LIMIT :lim")
    with engine.begin() as conn:
        rows = conn.execute(text("\n".join(parts)), params).all()
    return [
        ReleaseOut(
            id=r[0],
            build_id=r[1],
            git_sha=r[2],
            artifact_hash=r[3],
            test_report_hash=r[4],
            status=r[5],
            notes=r[6],
            promoted_at=r[7],
            created_at=r[8],
        )
        for r in rows
    ]


@router.post("/releases", response_model=ReleaseOut, status_code=status.HTTP_201_CREATED)
def register_release(user: SuperAdminUser, body: ReleaseRegisterIn) -> ReleaseOut:
    uid = user.id
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO ops_releases (
                  build_id, git_sha, artifact_hash, test_report_hash, notes, created_by_user_id
                )
                VALUES (:bid, :sha, :art, :test, :notes, CAST(:uid AS uuid))
                RETURNING id::text, build_id, git_sha, artifact_hash, test_report_hash,
                          status, notes, promoted_at, created_at
                """
            ),
            {
                "bid": body.build_id.strip(),
                "sha": body.git_sha,
                "art": body.artifact_hash,
                "test": body.test_report_hash,
                "notes": body.notes,
                "uid": uid,
            },
        ).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="release insert failed")
    return ReleaseOut(
        id=row[0],
        build_id=row[1],
        git_sha=row[2],
        artifact_hash=row[3],
        test_report_hash=row[4],
        status=row[5],
        notes=row[6],
        promoted_at=row[7],
        created_at=row[8],
    )


@router.post("/releases/{release_id}/promote", response_model=ReleaseOut)
def promote_release(user: SuperAdminUser, release_id: str) -> ReleaseOut:
    uid = user.id
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE ops_releases SET status = 'rolled_back'
                WHERE status = 'current'
                """
            )
        )
        row = conn.execute(
            text(
                """
                UPDATE ops_releases
                SET status = 'current',
                    promoted_at = now(),
                    promoted_by_user_id = CAST(:uid AS uuid)
                WHERE id = CAST(:id AS uuid)
                RETURNING id::text, build_id, git_sha, artifact_hash, test_report_hash,
                          status, notes, promoted_at, created_at
                """
            ),
            {"id": release_id, "uid": uid},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="release not found")
    return ReleaseOut(
        id=row[0],
        build_id=row[1],
        git_sha=row[2],
        artifact_hash=row[3],
        test_report_hash=row[4],
        status=row[5],
        notes=row[6],
        promoted_at=row[7],
        created_at=row[8],
    )
