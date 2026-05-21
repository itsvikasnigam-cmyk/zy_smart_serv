from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.ops_tasks import resolve_ops_task

from .deps import SuperAdminUser

router = APIRouter(prefix="/ops", tags=["ops-tasks"])


class OpsTaskOut(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    alert_type: str
    alert_dedupe_key: str | None = None
    summary: str
    detail_json: dict[str, Any]
    client_id: str | None = None
    sop_run_id: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolved_by_user_id: str | None = None
    resolution_note: str | None = None


class OpsTaskListOut(BaseModel):
    items: list[OpsTaskOut]
    next_cursor: str | None = None


class OpsTaskResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_note: str | None = Field(default=None, max_length=2000)


class OpsTaskEventOut(BaseModel):
    id: str
    action: str
    actor_user_id: str | None = None
    note: str | None = None
    created_at: datetime


def _row_to_task(r: Any) -> OpsTaskOut:
    return OpsTaskOut(
        id=r[0],
        title=r[1],
        status=r[2],
        priority=r[3],
        alert_type=r[4],
        alert_dedupe_key=r[5],
        summary=r[6],
        detail_json=r[7] if isinstance(r[7], dict) else {},
        client_id=r[8],
        sop_run_id=r[9],
        created_at=r[10],
        updated_at=r[11],
        resolved_at=r[12],
        resolved_by_user_id=r[13],
        resolution_note=r[14],
    )


@router.get("/tasks", response_model=OpsTaskListOut)
def list_ops_tasks(
    _user: SuperAdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> OpsTaskListOut:
    params: dict[str, Any] = {"lim": limit + 1}
    parts = [
        """
        SELECT
          id::text, title, status, priority, alert_type, alert_dedupe_key,
          summary, detail_json, client_id::text, sop_run_id::text,
          created_at, updated_at, resolved_at, resolved_by_user_id::text, resolution_note
        FROM ops_tasks
        WHERE 1=1
        """
    ]
    if status:
        parts.append("AND status = :st")
        params["st"] = status.strip()
    if cursor:
        parts.append("AND created_at < CAST(:cur AS timestamptz)")
        params["cur"] = cursor
    parts.append("ORDER BY created_at DESC LIMIT :lim")
    with engine.begin() as conn:
        rows = conn.execute(text("\n".join(parts)), params).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    items = [_row_to_task(r) for r in page]
    next_cursor = page[-1][10].isoformat() if has_more and page else None
    return OpsTaskListOut(items=items, next_cursor=next_cursor)


@router.post("/tasks/{task_id}/resolve", response_model=OpsTaskOut)
def resolve_task_api(
    user: SuperAdminUser,
    task_id: str,
    body: OpsTaskResolveIn,
) -> OpsTaskOut:
    with engine.begin() as conn:
        ok = resolve_ops_task(
            conn,
            task_id=task_id,
            resolved_by_user_id=user.id,
            resolution_note=body.resolution_note,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="task not found or not open")
        row = conn.execute(
            text(
                """
                SELECT
                  id::text, title, status, priority, alert_type, alert_dedupe_key,
                  summary, detail_json, client_id::text, sop_run_id::text,
                  created_at, updated_at, resolved_at, resolved_by_user_id::text, resolution_note
                FROM ops_tasks WHERE id = CAST(:tid AS uuid)
                """
            ),
            {"tid": task_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    return _row_to_task(row)


@router.get("/tasks/{task_id}/events", response_model=list[OpsTaskEventOut])
def list_task_events(_user: SuperAdminUser, task_id: str) -> list[OpsTaskEventOut]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id::text, action, actor_user_id::text, note, created_at
                FROM ops_task_events
                WHERE task_id = CAST(:tid AS uuid)
                ORDER BY created_at ASC
                """
            ),
            {"tid": task_id},
        ).all()
    return [
        OpsTaskEventOut(
            id=r[0],
            action=r[1],
            actor_user_id=r[2],
            note=r[3],
            created_at=r[4],
        )
        for r in rows
    ]
