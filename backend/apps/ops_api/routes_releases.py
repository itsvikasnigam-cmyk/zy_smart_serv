from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.release_manager import (
    APPROVAL_CHECKLIST_KEY,
    disable_canary_quick,
    load_canary_policy_conn,
    promote_release,
    register_release,
    rollback_release,
    save_canary_policy_conn,
)

from .deps import SuperAdminUser

router = APIRouter(prefix="/ops", tags=["ops-releases"])


class ReleaseOut(BaseModel):
    id: str
    build_id: str
    git_sha: str | None = None
    status: str
    artifact_hash: str | None = None
    test_report_hash: str | None = None
    registered_at: datetime
    promoted_at: datetime | None = None
    rolled_back_at: datetime | None = None
    notes: str | None = None


class ReleaseRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_id: str = Field(min_length=1, max_length=256)
    git_sha: str | None = Field(default=None, max_length=64)
    artifact_hash: str | None = Field(default=None, max_length=128)
    test_report_hash: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=4000)


class ReleasePromoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canary_percent: int = Field(default=0, ge=0, le=100)
    canary_primary_model: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=2000)


class ReleaseRollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class CanaryPolicyOut(BaseModel):
    enabled: bool
    percent: int
    active_build_id: str | None = None
    canary_primary_model: str | None = None


class CanaryPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    percent: int | None = Field(default=None, ge=0, le=100)
    active_build_id: str | None = None
    canary_primary_model: str | None = None


def _row_release(r: Any) -> ReleaseOut:
    return ReleaseOut(
        id=r[0],
        build_id=r[1],
        git_sha=r[2],
        status=r[3],
        artifact_hash=r[4],
        test_report_hash=r[5],
        registered_at=r[6],
        promoted_at=r[7],
        rolled_back_at=r[8],
        notes=r[9],
    )


@router.get("/releases", response_model=list[ReleaseOut])
def list_releases(
    _user: SuperAdminUser,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ReleaseOut]:
    parts = [
        """
        SELECT id::text, build_id, git_sha, status, artifact_hash, test_report_hash,
               registered_at, promoted_at, rolled_back_at, notes
        FROM ops_releases
        WHERE 1=1
        """
    ]
    params: dict[str, Any] = {"lim": limit}
    if status_filter:
        parts.append("AND status = :st")
        params["st"] = status_filter.strip()
    parts.append("ORDER BY registered_at DESC LIMIT :lim")
    with engine.begin() as conn:
        rows = conn.execute(text("\n".join(parts)), params).all()
    return [_row_release(r) for r in rows]


@router.post("/releases", response_model=ReleaseOut, status_code=status.HTTP_201_CREATED)
def create_release(user: SuperAdminUser, body: ReleaseRegisterIn) -> ReleaseOut:
    try:
        with engine.begin() as conn:
            rid = register_release(
                conn,
                build_id=body.build_id,
                git_sha=body.git_sha,
                artifact_hash=body.artifact_hash,
                test_report_hash=body.test_report_hash,
                notes=body.notes,
                actor_user_id=user.id,
            )
            row = conn.execute(
                text(
                    """
                    SELECT id::text, build_id, git_sha, status, artifact_hash, test_report_hash,
                           registered_at, promoted_at, rolled_back_at, notes
                    FROM ops_releases WHERE id = CAST(:rid AS uuid)
                    """
                ),
                {"rid": rid},
            ).fetchone()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=500, detail="register failed")
    return _row_release(row)


@router.post("/releases/{build_id}/promote", response_model=ReleaseOut)
def promote_release_api(user: SuperAdminUser, build_id: str, body: ReleasePromoteIn) -> ReleaseOut:
    try:
        with engine.begin() as conn:
            rid = promote_release(
                conn,
                build_id=build_id,
                actor_user_id=user.id,
                canary_percent=body.canary_percent,
                canary_primary_model=body.canary_primary_model,
                note=body.note,
            )
            row = conn.execute(
                text(
                    """
                    SELECT id::text, build_id, git_sha, status, artifact_hash, test_report_hash,
                           registered_at, promoted_at, rolled_back_at, notes
                    FROM ops_releases WHERE id = CAST(:rid AS uuid)
                    """
                ),
                {"rid": rid},
            ).fetchone()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _row_release(row)


@router.post("/releases/{build_id}/rollback", response_model=ReleaseOut)
def rollback_release_api(user: SuperAdminUser, build_id: str, body: ReleaseRollbackIn) -> ReleaseOut:
    try:
        with engine.begin() as conn:
            rid = rollback_release(
                conn,
                build_id=build_id,
                actor_user_id=user.id,
                note=body.note,
            )
            row = conn.execute(
                text(
                    """
                    SELECT id::text, build_id, git_sha, status, artifact_hash, test_report_hash,
                           registered_at, promoted_at, rolled_back_at, notes
                    FROM ops_releases WHERE id = CAST(:rid AS uuid)
                    """
                ),
                {"rid": rid},
            ).fetchone()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _row_release(row)


@router.get("/releases/canary", response_model=CanaryPolicyOut)
def get_canary_policy(_user: SuperAdminUser) -> CanaryPolicyOut:
    with engine.begin() as conn:
        p = load_canary_policy_conn(conn)
    return CanaryPolicyOut(
        enabled=p.enabled,
        percent=p.percent,
        active_build_id=p.active_build_id,
        canary_primary_model=p.canary_primary_model,
    )


@router.put("/releases/canary", response_model=CanaryPolicyOut)
def patch_canary_policy(user: SuperAdminUser, body: CanaryPatchIn) -> CanaryPolicyOut:
    with engine.begin() as conn:
        p = save_canary_policy_conn(
            conn,
            enabled=body.enabled,
            percent=body.percent,
            active_build_id=body.active_build_id,
            canary_primary_model=body.canary_primary_model,
        )
    return CanaryPolicyOut(
        enabled=p.enabled,
        percent=p.percent,
        active_build_id=p.active_build_id,
        canary_primary_model=p.canary_primary_model,
    )


@router.post("/releases/canary/disable", response_model=CanaryPolicyOut)
def disable_canary_api(_user: SuperAdminUser) -> CanaryPolicyOut:
    """Fast off-switch for canary traffic."""
    with engine.begin() as conn:
        p = disable_canary_quick(conn, note="POST /ops/releases/canary/disable")
    return CanaryPolicyOut(
        enabled=p.enabled,
        percent=p.percent,
        active_build_id=p.active_build_id,
        canary_primary_model=p.canary_primary_model,
    )


@router.get("/releases/approval-checklist")
def get_approval_checklist(_user: SuperAdminUser) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
            {"k": APPROVAL_CHECKLIST_KEY},
        ).fetchone()
    return row[0] if row and isinstance(row[0], dict) else {"items": []}
