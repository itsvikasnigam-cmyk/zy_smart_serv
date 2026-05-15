from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.shared.db import engine

from .deps import SuperAdminUser
from .models import (
    RunCreate,
    RunCreateResponse,
    RunListOut,
    RunOut,
    SopCreate,
    SopCreateResponse,
    SopDetailOut,
    SopSummaryOut,
    SopUpdate,
    SopVersionLightOut,
    SopVersionOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/sops", response_model=list[SopSummaryOut])
def list_sops(
    _user: SuperAdminUser,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    status: Annotated[str | None, Query(description="active|archived")] = None,
    q: Annotated[str | None, Query(description="Case-insensitive title search")] = None,
) -> list[SopSummaryOut]:
    parts = [
        """
        SELECT id::text, title, slug, category, status, current_version, created_at, updated_at
        FROM ops_sops
        WHERE 1=1
        """
    ]
    params: dict[str, object] = {}
    if category is not None and category != "":
        parts.append("AND category = :category")
        params["category"] = category
    if status is not None and status != "":
        parts.append("AND status = :status")
        params["status"] = status
    if q is not None and q.strip():
        parts.append("AND title ILIKE :title_pat")
        params["title_pat"] = f"%{q.strip()}%"
    parts.append("ORDER BY updated_at DESC")
    sql = "\n".join(parts)
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    return [
        SopSummaryOut(
            id=r[0],
            title=r[1],
            slug=r[2],
            category=r[3],
            status=r[4],
            current_version=r[5],
            created_at=r[6],
            updated_at=r[7],
        )
        for r in rows
    ]


@router.post("/sops", response_model=SopCreateResponse, status_code=status.HTTP_201_CREATED)
def create_sop(user: SuperAdminUser, body: SopCreate) -> SopCreateResponse:
    uid = user.id
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO ops_sops (title, slug, category, status, current_version, created_by_user_id, updated_by_user_id)
                    VALUES (:title, :slug, :category, :status, 1, CAST(:uid AS uuid), CAST(:uid AS uuid))
                    RETURNING id::text, current_version
                    """
                ),
                {
                    "title": body.title.strip(),
                    "slug": body.slug.strip().lower(),
                    "category": body.category.strip() if body.category else None,
                    "status": body.status,
                    "uid": uid,
                },
            ).fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="insert failed")
            sid, ver = row[0], int(row[1])
            conn.execute(
                text(
                    """
                    INSERT INTO ops_sop_versions (sop_id, version_num, body_markdown, created_by_user_id)
                    VALUES (CAST(:sid AS uuid), 1, :body, CAST(:uid AS uuid))
                    """
                ),
                {"sid": sid, "body": body.body_markdown, "uid": uid},
            )
    except IntegrityError as e:
        logger.info("create_sop integrity error: %s", e)
        raise HTTPException(status_code=409, detail="slug already exists or invalid reference") from e
    return SopCreateResponse(id=sid, current_version=ver)


@router.get("/sops/{sop_id}", response_model=SopDetailOut)
def get_sop(_user: SuperAdminUser, sop_id: str) -> SopDetailOut:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT s.id::text, s.title, s.slug, s.category, s.status, s.current_version,
                       s.created_at, s.updated_at, v.body_markdown
                FROM ops_sops s
                JOIN ops_sop_versions v ON v.sop_id = s.id AND v.version_num = s.current_version
                WHERE s.id = CAST(:id AS uuid)
                LIMIT 1
                """
            ),
            {"id": sop_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="sop not found")
    return SopDetailOut(
        id=row[0],
        title=row[1],
        slug=row[2],
        category=row[3],
        status=row[4],
        current_version=row[5],
        created_at=row[6],
        updated_at=row[7],
        body_markdown=row[8],
    )


@router.get("/sops/{sop_id}/versions", response_model=list[SopVersionOut] | list[SopVersionLightOut])
def list_sop_versions(
    _user: SuperAdminUser,
    sop_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    before_version: Annotated[int | None, Query(ge=1, description="Return versions < this number")] = None,
    include_body: Annotated[bool, Query(description="When false, omit body_markdown (timeline UI)")] = True,
) -> list[SopVersionOut] | list[SopVersionLightOut]:
    """Immutable version history; optional paging and light rows without markdown bodies."""
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM ops_sops WHERE id = CAST(:id AS uuid) LIMIT 1"),
            {"id": sop_id},
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="sop not found")
        parts = [
            """
            SELECT v.version_num, v.body_markdown, v.created_at, v.created_by_user_id::text
            FROM ops_sop_versions v
            WHERE v.sop_id = CAST(:sid AS uuid)
            """
        ]
        params: dict[str, object] = {"sid": sop_id, "lim": limit}
        if before_version is not None:
            parts.append("AND v.version_num < :bv")
            params["bv"] = before_version
        parts.append("ORDER BY v.version_num DESC")
        parts.append("LIMIT :lim")
        rows = conn.execute(text("\n".join(parts)), params).all()
    rows = list(reversed(rows))
    if not include_body:
        return [
            SopVersionLightOut(
                version_num=int(r[0]),
                created_at=r[2],
                created_by_user_id=r[3],
            )
            for r in rows
        ]
    return [
        SopVersionOut(
            version_num=int(r[0]),
            body_markdown=r[1],
            created_at=r[2],
            created_by_user_id=r[3],
        )
        for r in rows
    ]


@router.put("/sops/{sop_id}", response_model=SopCreateResponse)
def update_sop(user: SuperAdminUser, sop_id: str, body: SopUpdate) -> SopCreateResponse:
    uid = user.id
    try:
        with engine.begin() as conn:
            cur = conn.execute(
                text(
                    """
                    SELECT current_version FROM ops_sops WHERE id = CAST(:id AS uuid) LIMIT 1
                    """
                ),
                {"id": sop_id},
            ).fetchone()
            if not cur:
                raise HTTPException(status_code=404, detail="sop not found")
            next_v = int(cur[0]) + 1
            conn.execute(
                text(
                    """
                    INSERT INTO ops_sop_versions (sop_id, version_num, body_markdown, created_by_user_id)
                    VALUES (CAST(:sid AS uuid), :ver, :body, CAST(:uid AS uuid))
                    """
                ),
                {"sid": sop_id, "ver": next_v, "body": body.body_markdown, "uid": uid},
            )
            conn.execute(
                text(
                    """
                    UPDATE ops_sops
                    SET title = :title,
                        category = :category,
                        status = :status,
                        current_version = :ver,
                        updated_by_user_id = CAST(:uid AS uuid),
                        updated_at = now()
                    WHERE id = CAST(:sid AS uuid)
                    """
                ),
                {
                    "title": body.title.strip(),
                    "category": body.category.strip() if body.category else None,
                    "status": body.status,
                    "ver": next_v,
                    "uid": uid,
                    "sid": sop_id,
                },
            )
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.info("update_sop integrity error: %s", e)
        raise HTTPException(status_code=409, detail="version conflict") from e
    return SopCreateResponse(id=sop_id, current_version=next_v)


@router.post("/sops/{sop_id}/run", response_model=RunCreateResponse, status_code=status.HTTP_201_CREATED)
def start_run(user: SuperAdminUser, sop_id: str, body: RunCreate) -> RunCreateResponse:
    uid = user.id
    cid = (body.client_id or "").strip() or None
    if cid:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM api_clients WHERE id = CAST(:cid AS uuid) LIMIT 1"),
                {"cid": cid},
            ).fetchone()
        if not exists:
            raise HTTPException(status_code=400, detail="client_id not found")
    try:
        with engine.begin() as conn:
            srow = conn.execute(
                text(
                    "SELECT current_version FROM ops_sops WHERE id = CAST(:id AS uuid) LIMIT 1",
                ),
                {"id": sop_id},
            ).fetchone()
            if not srow:
                raise HTTPException(status_code=404, detail="sop not found")
            ver = int(srow[0])
            ins = conn.execute(
                text(
                    """
                    INSERT INTO ops_run_logs (
                      sop_id, sop_version_at_run, context_json, trigger_type,
                      created_by_user_id, client_id
                    )
                    VALUES (
                      CAST(:sid AS uuid), :ver, CAST(:ctx AS jsonb), :trig,
                      CAST(:uid AS uuid),
                      CAST(:cid AS uuid)
                    )
                    RETURNING id::text
                    """
                ),
                {
                    "sid": sop_id,
                    "ver": ver,
                    "ctx": json.dumps(body.context_json),
                    "trig": body.trigger_type,
                    "uid": uid,
                    "cid": cid,
                },
            ).fetchone()
            if not ins:
                raise HTTPException(status_code=500, detail="run insert failed")
            rid = ins[0]
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.info("start_run integrity error: %s", e)
        raise HTTPException(status_code=400, detail="invalid sop or user reference") from e
    return RunCreateResponse(id=rid, sop_id=sop_id, sop_version_at_run=ver)


@router.get("/runs", response_model=RunListOut)
def list_runs(
    _user: SuperAdminUser,
    client_id: Annotated[str | None, Query(description="Filter by linked api_clients.id")] = None,
    sop_id: Annotated[str | None, Query(description="Filter by SOP id")] = None,
    trigger_type: Annotated[str | None, Query()] = None,
    from_date: Annotated[date | None, Query(description="UTC date inclusive (created_at::date)")] = None,
    to_date: Annotated[date | None, Query(description="UTC date inclusive")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query(description="created_at|run_id for next page")] = None,
) -> RunListOut:
    parts = [
        """
        SELECT id::text, sop_id::text, sop_version_at_run, context_json, trigger_type,
               created_by_user_id::text, client_id::text, created_at
        FROM ops_run_logs
        WHERE 1=1
        """
    ]
    params: dict[str, object] = {}
    if sop_id:
        parts.append("AND sop_id = CAST(:sop_id AS uuid)")
        params["sop_id"] = sop_id
    if client_id:
        parts.append("AND client_id = CAST(:client_id AS uuid)")
        params["client_id"] = client_id
    if trigger_type:
        parts.append("AND trigger_type = :trigger_type")
        params["trigger_type"] = trigger_type
    if from_date is not None:
        parts.append("AND created_at::date >= :from_date")
        params["from_date"] = from_date
    if to_date is not None:
        parts.append("AND created_at::date <= :to_date")
        params["to_date"] = to_date
    if cursor:
        try:
            ts_s, rid = cursor.split("|", 1)
            params["c_ts"] = datetime.fromisoformat(ts_s.replace("Z", "+00:00"))
            params["c_id"] = rid
            parts.append("AND (created_at, id) < (:c_ts, CAST(:c_id AS uuid))")
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail="invalid cursor") from e
    parts.append("ORDER BY created_at DESC, id DESC")
    params["lim"] = limit + 1
    parts.append("LIMIT :lim")
    sql = "\n".join(parts)
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    out: list[RunOut] = []
    for r in page:
        ctx = r[3]
        if ctx is not None and not isinstance(ctx, dict):
            ctx = dict(ctx)  # type: ignore[arg-type]
        out.append(
            RunOut(
                id=r[0],
                sop_id=r[1],
                sop_version_at_run=int(r[2]),
                context_json=ctx if isinstance(ctx, dict) else {},
                trigger_type=str(r[4]),
                created_by_user_id=r[5],
                client_id=r[6],
                created_at=r[7],
            )
        )
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = f"{last[7].isoformat()}|{last[0]}"
    return RunListOut(items=out, next_cursor=next_cursor)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(_user: SuperAdminUser, run_id: str) -> RunOut:
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT id::text, sop_id::text, sop_version_at_run, context_json, trigger_type,
                       created_by_user_id::text, client_id::text, created_at
                FROM ops_run_logs
                WHERE id = CAST(:id AS uuid)
                LIMIT 1
                """
            ),
            {"id": run_id},
        ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    ctx = r[3]
    if ctx is not None and not isinstance(ctx, dict):
        ctx = dict(ctx)  # type: ignore[arg-type]
    return RunOut(
        id=r[0],
        sop_id=r[1],
        sop_version_at_run=int(r[2]),
        context_json=ctx if isinstance(ctx, dict) else {},
        trigger_type=str(r[4]),
        created_by_user_id=r[5],
        client_id=r[6],
        created_at=r[7],
    )
