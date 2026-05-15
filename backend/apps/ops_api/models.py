from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SopStatus = Literal["active", "archived"]
TriggerType = Literal[
    "manual",
    "auto",
    "scheduled",
    "other",
    "alert:outbox_dead_spike",
    "alert:meta_webhook_error_spike",
]


class SopCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: str | None = Field(default=None, max_length=200)
    status: SopStatus = "active"
    body_markdown: str = Field(min_length=1)


class SopUpdate(BaseModel):
    """PUT: replaces mutable fields; always appends a new immutable version row."""

    title: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=200)
    status: SopStatus
    body_markdown: str = Field(min_length=1)


class SopSummaryOut(BaseModel):
    id: str
    title: str
    slug: str
    category: str | None
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class SopDetailOut(SopSummaryOut):
    body_markdown: str


class SopVersionOut(BaseModel):
    """Immutable history row from `ops_sop_versions`."""

    version_num: int
    body_markdown: str
    created_at: datetime
    created_by_user_id: str | None = None


class SopCreateResponse(BaseModel):
    id: str
    current_version: int


class RunCreate(BaseModel):
    """Context for Chat H: client_id, wa_number_id, error codes, outbox ids, free text, etc."""

    context_json: dict[str, Any] = Field(default_factory=dict)
    trigger_type: TriggerType = "manual"
    client_id: str | None = Field(
        default=None,
        description="Optional UUID; stored for GET /ops/runs filtering and dashboards.",
    )


class RunOut(BaseModel):
    id: str
    sop_id: str
    sop_version_at_run: int
    context_json: dict[str, Any]
    trigger_type: str
    created_by_user_id: str | None
    client_id: str | None
    created_at: datetime


class RunCreateResponse(BaseModel):
    id: str
    sop_id: str
    sop_version_at_run: int


class RunListOut(BaseModel):
    items: list[RunOut]
    next_cursor: str | None = None


class SopVersionLightOut(BaseModel):
    version_num: int
    created_at: datetime
    created_by_user_id: str | None = None
