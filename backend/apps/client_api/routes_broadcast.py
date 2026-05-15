from __future__ import annotations

"""M6: tenant broadcast opt-in + campaign REST (worker enqueues wa_outbox TEMPLATE rows)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.shared.db import engine

from .auth import ROLE_OWNER, ROLE_SUPER_ADMIN
from .deps import CurrentUser, get_current_user, require_roles, resolve_client_scope

router = APIRouter(tags=["broadcast"], prefix="/broadcast")


class OptInPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_phone_e164: str = Field(min_length=8, max_length=20)
    opted_in: bool
    source: str | None = Field(default=None, max_length=100)


class OptInOut(BaseModel):
    client_id: str
    customer_phone_e164: str
    opted_in: bool
    source: str | None
    updated_at: str | None


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_wa_number_id: str
    template_name: str = Field(min_length=1, max_length=200)
    template_language: str = Field(default="en_US", max_length=20)
    target_chat_ids: list[str] = Field(min_length=1, max_length=5000)


class CampaignOut(BaseModel):
    id: str
    client_id: str
    from_wa_number_id: str
    template_name: str
    template_language: str
    status: str
    created_at: str
    target_count: int = 0


OwnerUser = Annotated[CurrentUser, Depends(require_roles(ROLE_OWNER, ROLE_SUPER_ADMIN))]


def _scope(user: OwnerUser, client_id: str | None) -> str:
    return resolve_client_scope(user, explicit_client_id=client_id)


@router.put("/opt-in", response_model=OptInOut)
def put_marketing_opt_in(
    body: OptInPut,
    user: OwnerUser,
    client_id: Annotated[str | None, Query()] = None,
) -> OptInOut:
    cid = _scope(user, client_id)
    phone = body.customer_phone_e164.strip()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO customer_marketing_opt_in (
                  client_id, customer_phone_e164, opted_in, source, updated_at
                )
                VALUES (CAST(:cid AS uuid), :phone, :opt, :src, now())
                ON CONFLICT (client_id, customer_phone_e164) DO UPDATE
                SET opted_in = EXCLUDED.opted_in,
                    source = EXCLUDED.source,
                    updated_at = now()
                RETURNING client_id::text, customer_phone_e164, opted_in, source, updated_at
                """
            ),
            {"cid": cid, "phone": phone, "opt": body.opted_in, "src": body.source},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="opt-in upsert failed")
    return OptInOut(
        client_id=row[0],
        customer_phone_e164=row[1],
        opted_in=bool(row[2]),
        source=row[3],
        updated_at=row[4].isoformat() if row[4] else None,
    )


@router.get("/opt-in", response_model=list[OptInOut])
def list_marketing_opt_in(
    user: OwnerUser,
    client_id: Annotated[str | None, Query()] = None,
    opted_in: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[OptInOut]:
    cid = _scope(user, client_id)
    parts = [
        """
        SELECT client_id::text, customer_phone_e164, opted_in, source, updated_at
        FROM customer_marketing_opt_in
        WHERE client_id = CAST(:cid AS uuid)
        """
    ]
    params: dict[str, Any] = {"cid": cid, "lim": limit}
    if opted_in is not None:
        parts.append("AND opted_in = :opt")
        params["opt"] = opted_in
    parts.append("ORDER BY updated_at DESC LIMIT :lim")
    with engine.begin() as conn:
        rows = conn.execute(text("\n".join(parts)), params).all()
    return [
        OptInOut(
            client_id=r[0],
            customer_phone_e164=r[1],
            opted_in=bool(r[2]),
            source=r[3],
            updated_at=r[4].isoformat() if r[4] else None,
        )
        for r in rows
    ]


@router.post("/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    body: CampaignCreate,
    user: OwnerUser,
    client_id: Annotated[str | None, Query()] = None,
) -> CampaignOut:
    cid = _scope(user, client_id)
    with engine.begin() as conn:
        wn = conn.execute(
            text(
                """
                SELECT 1 FROM wa_numbers
                WHERE id = CAST(:wid AS uuid) AND client_id = CAST(:cid AS uuid)
                """
            ),
            {"wid": body.from_wa_number_id, "cid": cid},
        ).fetchone()
        if not wn:
            raise HTTPException(status_code=400, detail="from_wa_number_id not found for client")
        camp = conn.execute(
            text(
                """
                INSERT INTO wa_broadcast_campaigns (
                  client_id, from_wa_number_id, template_name, template_language,
                  status, created_by_user_id
                )
                VALUES (
                  CAST(:cid AS uuid), CAST(:wid AS uuid), :tn, :tl,
                  'queued', CAST(:uid AS uuid)
                )
                RETURNING id::text, created_at
                """
            ),
            {
                "cid": cid,
                "wid": body.from_wa_number_id,
                "tn": body.template_name.strip(),
                "tl": body.template_language.strip(),
                "uid": user.id,
            },
        ).fetchone()
        if not camp:
            raise HTTPException(status_code=500, detail="campaign insert failed")
        camp_id, created_at = camp[0], camp[1]
        inserted = 0
        for chat_id in body.target_chat_ids:
            chat = conn.execute(
                text(
                    """
                    SELECT customer_phone FROM inbox_chats
                    WHERE id = CAST(:chid AS uuid) AND client_id = CAST(:cid AS uuid)
                    """
                ),
                {"chid": chat_id, "cid": cid},
            ).fetchone()
            if not chat:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO wa_broadcast_targets (campaign_id, chat_id, customer_phone_e164)
                    VALUES (CAST(:camp AS uuid), CAST(:chid AS uuid), :phone)
                    ON CONFLICT (campaign_id, chat_id) DO NOTHING
                    """
                ),
                {"camp": camp_id, "chid": chat_id, "phone": chat[0]},
            )
            inserted += 1
    return CampaignOut(
        id=camp_id,
        client_id=cid,
        from_wa_number_id=body.from_wa_number_id,
        template_name=body.template_name,
        template_language=body.template_language,
        status="queued",
        created_at=created_at.isoformat() if created_at else "",
        target_count=inserted,
    )


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(
    user: OwnerUser,
    client_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[CampaignOut]:
    cid = _scope(user, client_id)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.id::text, c.client_id::text, c.from_wa_number_id::text,
                       c.template_name, c.template_language, c.status, c.created_at,
                       (SELECT count(*)::int FROM wa_broadcast_targets t WHERE t.campaign_id = c.id)
                FROM wa_broadcast_campaigns c
                WHERE c.client_id = CAST(:cid AS uuid)
                ORDER BY c.created_at DESC
                LIMIT :lim
                """
            ),
            {"cid": cid, "lim": limit},
        ).all()
    return [
        CampaignOut(
            id=r[0],
            client_id=r[1],
            from_wa_number_id=r[2],
            template_name=r[3],
            template_language=r[4],
            status=r[5],
            created_at=r[6].isoformat() if r[6] else "",
            target_count=int(r[7] or 0),
        )
        for r in rows
    ]


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: str,
    user: OwnerUser,
    client_id: Annotated[str | None, Query()] = None,
) -> CampaignOut:
    cid = _scope(user, client_id)
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT c.id::text, c.client_id::text, c.from_wa_number_id::text,
                       c.template_name, c.template_language, c.status, c.created_at,
                       (SELECT count(*)::int FROM wa_broadcast_targets t WHERE t.campaign_id = c.id)
                FROM wa_broadcast_campaigns c
                WHERE c.id = CAST(:id AS uuid) AND c.client_id = CAST(:cid AS uuid)
                """
            ),
            {"id": campaign_id, "cid": cid},
        ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="campaign not found")
    return CampaignOut(
        id=r[0],
        client_id=r[1],
        from_wa_number_id=r[2],
        template_name=r[3],
        template_language=r[4],
        status=r[5],
        created_at=r[6].isoformat() if r[6] else "",
        target_count=int(r[7] or 0),
    )
