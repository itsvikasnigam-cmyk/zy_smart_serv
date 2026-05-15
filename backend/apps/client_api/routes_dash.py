from __future__ import annotations

"""Read-only dashboard routes (M8 / Chat J).

* ``/dash/client/*`` — ``owner``, ``agent``, or ``super_admin`` (latter must pass ``client_id``).
* ``/dash/admin/*`` — ``super_admin`` only (system-wide aggregates).

Aggregates read existing tables; metrics rollups may be empty until workers run.
**Billing:** subscription tier and provider truth live in ``billing_api`` + core tables
(``api_clients``, ``bill_subscriptions``, ``bill_invoices``); these routes do **not** call Razorpay/Paddle.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from backend.shared.db import engine

from .auth import ROLE_AGENT, ROLE_OWNER, ROLE_SUPER_ADMIN
from .deps import CurrentUser, require_roles, resolve_client_scope
from .models import (
    DashAdminCollectionsOut,
    DashAdminGeoOut,
    DashAdminGeoRow,
    DashAdminOpsWhatsappOut,
    DashAdminOverviewOut,
    DashAdminProviderOut,
    DashAgentRow,
    DashClientAgentsOut,
    DashClientOverviewOut,
    DashClientQualityOut,
    DashMessageTotals,
    DashUsageToday,
)

router = APIRouter(tags=["dash"], prefix="/dash")

ClientDashUser = Annotated[CurrentUser, Depends(require_roles(ROLE_OWNER, ROLE_AGENT, ROLE_SUPER_ADMIN))]
AdminDashUser = Annotated[CurrentUser, Depends(require_roles(ROLE_SUPER_ADMIN))]


def _scoped_client_id(
    user: ClientDashUser,
    client_id: Annotated[str | None, Query(description="Required for super_admin; ignored for owner/agent")] = None,
) -> str:
    return resolve_client_scope(user, explicit_client_id=client_id)


ScopedClientId = Annotated[str, Depends(_scoped_client_id)]


def _row_to_usage_today(row: object | None) -> DashUsageToday:
    if not row:
        return DashUsageToday()
    return DashUsageToday(
        usage_date=str(row[0]) if row[0] is not None else None,
        inbound_customer_messages=int(row[1] or 0),
        outbound_ai_messages=int(row[2] or 0),
        outbound_agent_messages=int(row[3] or 0),
        outbound_system_messages=int(row[4] or 0),
        soft_threshold_crossed_at=row[5],
        hard_threshold_crossed_at=row[6],
    )


def _rows_to_totals(row: object | None) -> DashMessageTotals:
    if not row:
        return DashMessageTotals()
    return DashMessageTotals(
        customer=int(row[0] or 0),
        ai=int(row[1] or 0),
        agent=int(row[2] or 0),
        system=int(row[3] or 0),
    )


@router.get("/client/overview", response_model=DashClientOverviewOut)
def dash_client_overview(client_id: ScopedClientId) -> DashClientOverviewOut:
    with engine.begin() as conn:
        crow = conn.execute(
            text(
                """
                SELECT business_name, entitlement_plan, billing_provider, trial_end
                FROM api_clients
                WHERE id = CAST(:cid AS uuid)
                """
            ),
            {"cid": client_id},
        ).fetchone()
        if not crow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")

        st_rows = conn.execute(
            text(
                """
                SELECT state, count(*)::int
                FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                GROUP BY state
                """
            ),
            {"cid": client_id},
        ).all()
        wn = conn.execute(
            text(
                """
                SELECT count(*)::int FROM wa_numbers
                WHERE client_id = CAST(:cid AS uuid)
                """
            ),
            {"cid": client_id},
        ).scalar_one()

        usage_row = conn.execute(
            text(
                """
                SELECT usage_date,
                       inbound_customer_messages,
                       outbound_ai_messages,
                       outbound_agent_messages,
                       outbound_system_messages,
                       soft_threshold_crossed_at,
                       hard_threshold_crossed_at
                FROM bill_usage_daily
                WHERE client_id = CAST(:cid AS uuid)
                  AND usage_date = (timezone('utc', now()))::date
                """
            ),
            {"cid": client_id},
        ).fetchone()

        m7 = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(customer_messages), 0)::bigint,
                       COALESCE(SUM(ai_messages), 0)::bigint,
                       COALESCE(SUM(agent_messages), 0)::bigint,
                       COALESCE(SUM(system_messages), 0)::bigint
                FROM metrics_daily_client
                WHERE client_id = CAST(:cid AS uuid)
                  AND metric_date >= (timezone('utc', now()))::date - 7
                """
            ),
            {"cid": client_id},
        ).fetchone()

    chats_by_state = {str(r[0]): int(r[1]) for r in st_rows}
    m7t = _rows_to_totals(m7)

    return DashClientOverviewOut(
        client_id=client_id,
        business_name=crow[0],
        entitlement_plan=crow[1],
        billing_provider=crow[2],
        trial_end=crow[3],
        wa_numbers_count=int(wn or 0),
        chats_by_state=chats_by_state,
        usage_today=_row_to_usage_today(usage_row),
        messages_last_7d=m7t,
    )


@router.get("/client/agents", response_model=DashClientAgentsOut)
def dash_client_agents(client_id: ScopedClientId) -> DashClientAgentsOut:
    with engine.begin() as conn:
        active_rows = conn.execute(
            text(
                """
                SELECT assigned_agent_id::text, count(*)::int
                FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                  AND state = 'AGENT_ACTIVE'
                  AND assigned_agent_id IS NOT NULL
                GROUP BY assigned_agent_id
                """
            ),
            {"cid": client_id},
        ).all()
        active_map = {r[0]: int(r[1]) for r in active_rows}

        agent_rows = conn.execute(
            text(
                """
                SELECT u.id::text, u.name, u.email,
                       COALESCE(SUM(m.replies_count), 0)::bigint AS replies_7d
                FROM api_users u
                LEFT JOIN metrics_daily_agent m
                  ON m.agent_user_id = u.id
                 AND m.client_id = u.client_id
                 AND m.metric_date >= (timezone('utc', now()))::date - 7
                WHERE u.client_id = CAST(:cid AS uuid)
                  AND u.role = 'agent'
                GROUP BY u.id, u.name, u.email
                ORDER BY replies_7d DESC, lower(coalesce(u.name, u.email, ''))
                """
            ),
            {"cid": client_id},
        ).all()

    agents = [
        DashAgentRow(
            user_id=r[0],
            name=r[1],
            email=r[2],
            replies_last_7d=int(r[3] or 0),
            active_assigned_chats=active_map.get(r[0], 0),
        )
        for r in agent_rows
    ]
    return DashClientAgentsOut(client_id=client_id, agents=agents)


@router.get("/client/quality", response_model=DashClientQualityOut)
def dash_client_quality(client_id: ScopedClientId) -> DashClientQualityOut:
    with engine.begin() as conn:
        pending = conn.execute(
            text(
                """
                SELECT count(*)::int
                FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                  AND state IN ('HUMAN_REQ', 'WAITING_OWNER_DATA')
                """
            ),
            {"cid": client_id},
        ).scalar_one()

        handoff_7d = conn.execute(
            text(
                """
                SELECT count(*)::int
                FROM inbox_chats
                WHERE client_id = CAST(:cid AS uuid)
                  AND handoff_reason IS NOT NULL
                  AND COALESCE(last_customer_msg_at, created_at)
                        >= (timezone('utc', now()) - interval '7 days')
                """
            ),
            {"cid": client_id},
        ).scalar_one()

        m7 = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(customer_messages), 0)::bigint,
                       COALESCE(SUM(ai_messages), 0)::bigint,
                       COALESCE(SUM(agent_messages), 0)::bigint,
                       COALESCE(SUM(system_messages), 0)::bigint
                FROM metrics_daily_client
                WHERE client_id = CAST(:cid AS uuid)
                  AND metric_date >= (timezone('utc', now()))::date - 7
                """
            ),
            {"cid": client_id},
        ).fetchone()

    return DashClientQualityOut(
        client_id=client_id,
        chats_pending_agent=int(pending or 0),
        chats_with_handoff_reason_7d=int(handoff_7d or 0),
        median_first_response_seconds=None,
        csat_placeholder=None,
        messages_last_7d=_rows_to_totals(m7),
    )


@router.get("/admin/overview", response_model=DashAdminOverviewOut)
def dash_admin_overview(_user: AdminDashUser) -> DashAdminOverviewOut:
    with engine.begin() as conn:
        total_clients = int(
            conn.execute(text("SELECT count(*)::int FROM api_clients")).scalar_one() or 0
        )
        ent_rows = conn.execute(
            text(
                """
                SELECT entitlement_plan, count(*)::int
                FROM api_clients
                GROUP BY entitlement_plan
                """
            )
        ).all()
        total_chats = int(conn.execute(text("SELECT count(*)::int FROM inbox_chats")).scalar_one() or 0)
        total_wa = int(conn.execute(text("SELECT count(*)::int FROM wa_numbers")).scalar_one() or 0)

        ob_rows = conn.execute(
            text(
                """
                SELECT status, count(*)::int
                FROM wa_outbox
                GROUP BY status
                """
            )
        ).all()

        hourly = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(customer_in_messages), 0)::bigint,
                       COALESCE(SUM(ai_out_messages), 0)::bigint,
                       COALESCE(SUM(agent_out_messages), 0)::bigint,
                       COALESCE(SUM(wa_outbox_rows_dead), 0)::bigint,
                       COALESCE(SUM(wa_outbox_rows_created), 0)::bigint
                FROM metrics_hourly_system
                WHERE hour_bucket_utc >= timezone('utc', now()) - interval '24 hours'
                """
            )
        ).fetchone()

        hourly_dead = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(wa_outbox_rows_dead), 0)::bigint,
                       COALESCE(SUM(wa_outbox_rows_created), 0)::bigint
                FROM metrics_hourly_system
                WHERE hour_bucket_utc >= timezone('utc', now()) - interval '48 hours'
                """
            )
        ).fetchone()
        alerts_24h = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)::int FROM ops_alert_events
                    WHERE created_at >= timezone('utc', now()) - interval '24 hours'
                    """
                )
            ).scalar_one()
            or 0
        )

    clients_by_entitlement = {str(r[0]): int(r[1]) for r in ent_rows if r[0] is not None}
    outbox_by_status = {str(r[0]): int(r[1]) for r in ob_rows}

    hourly_totals = DashMessageTotals(
        customer=int(hourly[0] or 0) if hourly else 0,
        ai=int(hourly[1] or 0) if hourly else 0,
        agent=int(hourly[2] or 0) if hourly else 0,
        system=0,
    )
    dead_48 = int(hourly_dead[0] or 0) if hourly_dead else 0
    created_48 = int(hourly_dead[1] or 0) if hourly_dead else 0

    return DashAdminOverviewOut(
        total_clients=total_clients,
        clients_by_entitlement=clients_by_entitlement,
        total_chats=total_chats,
        total_wa_numbers=total_wa,
        outbox_by_status=outbox_by_status,
        hourly_system_last_24h=hourly_totals,
        hourly_outbox_dead_last_48h=dead_48,
        hourly_outbox_created_last_48h=created_48,
        ops_alerts_last_24h=alerts_24h,
    )


@router.get("/admin/collections", response_model=DashAdminCollectionsOut)
def dash_admin_collections(_user: AdminDashUser) -> DashAdminCollectionsOut:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT provider, status, count(*)::int
                FROM bill_subscriptions
                GROUP BY provider, status
                """
            )
        ).all()
        inv = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(amount_minor), 0)::bigint,
                       count(*)::int
                FROM bill_invoices
                WHERE status IN ('paid', 'completed', 'success')
                  AND issued_at >= date_trunc('month', timezone('utc', now()))
                """
            )
        ).fetchone()
        alert_cnt = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)::int FROM ops_alert_events
                    WHERE created_at >= timezone('utc', now()) - interval '24 hours'
                    """
                )
            ).scalar_one()
            or 0
        )

    by_provider: dict[str, int] = {}
    by_status: dict[str, int] = {}
    active_like = (
        "active",
        "live",
        "paid",
        "trialing",
        "authenticated",
        "trial",
        "processing",
    )
    active_subscriptions = 0
    for prov, st, cnt in rows:
        c = int(cnt or 0)
        pk = str(prov) if prov else "unknown"
        by_provider[pk] = by_provider.get(pk, 0) + c
        sk = str(st) if st else "unknown"
        by_status[sk] = by_status.get(sk, 0) + c
        if st and str(st).lower() in active_like:
            active_subscriptions += c

    revenue_mtd = int(inv[0] or 0) if inv else 0
    invoices_paid_mtd = int(inv[1] or 0) if inv else 0

    return DashAdminCollectionsOut(
        active_subscriptions=active_subscriptions,
        by_provider=by_provider,
        by_status=by_status,
        estimated_mrr_minor_units=revenue_mtd,
        notes=(
            f"estimated_mrr_minor_units uses paid invoice sum MTD ({revenue_mtd} minor units, "
            f"{invoices_paid_mtd} invoices). alerts_24h={alert_cnt}."
        ),
    )


def _dash_provider_detail(provider: str) -> DashAdminProviderOut:
    with engine.begin() as conn:
        st_rows = conn.execute(
            text(
                """
                SELECT status, count(*)::int
                FROM bill_subscriptions
                WHERE provider = :p
                GROUP BY status
                """
            ),
            {"p": provider},
        ).all()
        ev = conn.execute(
            text(
                """
                SELECT count(*)::int
                FROM bill_events
                WHERE provider = :p
                  AND received_at >= timezone('utc', now()) - interval '7 days'
                """
            ),
            {"p": provider},
        ).scalar_one()
        plans = conn.execute(
            text(
                """
                SELECT count(*)::int
                FROM bill_plans
                WHERE provider = :p
                """
            ),
            {"p": provider},
        ).scalar_one()

    subs_by_status = {str(r[0]): int(r[1]) for r in st_rows if r[0] is not None}
    return DashAdminProviderOut(
        provider=provider,  # type: ignore[arg-type]
        subscriptions_by_status=subs_by_status,
        events_last_7d=int(ev or 0),
        plans_configured=int(plans or 0),
    )


@router.get("/admin/providers/razorpay", response_model=DashAdminProviderOut)
def dash_admin_provider_rzp(_user: AdminDashUser) -> DashAdminProviderOut:
    return _dash_provider_detail("razorpay")


@router.get("/admin/providers/paddle", response_model=DashAdminProviderOut)
def dash_admin_provider_paddle(_user: AdminDashUser) -> DashAdminProviderOut:
    return _dash_provider_detail("paddle")


@router.get("/admin/ops/whatsapp", response_model=DashAdminOpsWhatsappOut)
def dash_admin_ops_whatsapp(_user: AdminDashUser) -> DashAdminOpsWhatsappOut:
    with engine.begin() as conn:
        wn = conn.execute(
            text(
                """
                SELECT type, count(*)::int
                FROM wa_numbers
                GROUP BY type
                """
            )
        ).all()
        ob_s = conn.execute(
            text(
                """
                SELECT status, count(*)::int
                FROM wa_outbox
                GROUP BY status
                """
            )
        ).all()
        ob_k = conn.execute(
            text(
                """
                SELECT kind, count(*)::int
                FROM wa_outbox
                GROUP BY kind
                """
            )
        ).all()

    return DashAdminOpsWhatsappOut(
        wa_numbers_by_type={str(r[0]): int(r[1]) for r in wn},
        outbox_by_status={str(r[0]): int(r[1]) for r in ob_s},
        outbox_by_kind={str(r[0]): int(r[1]) for r in ob_k},
    )


def _dash_admin_geo_body() -> DashAdminGeoOut:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COALESCE(NULLIF(trim(country_code), ''), 'unknown') AS cc, count(*)::int AS n
                FROM wa_numbers
                GROUP BY COALESCE(NULLIF(trim(country_code), ''), 'unknown')
                ORDER BY n DESC, cc
                """
            )
        ).all()

    return DashAdminGeoOut(rows=[DashAdminGeoRow(country_code=str(r[0]), wa_numbers=int(r[1])) for r in rows])


@router.get("/admin/geo", response_model=DashAdminGeoOut)
def dash_admin_geo(_user: AdminDashUser) -> DashAdminGeoOut:
    return _dash_admin_geo_body()


@router.get(
    "/admin/admin/geo",
    response_model=DashAdminGeoOut,
    summary="Geo (checklist path alias)",
    description="Same payload as ``GET /dash/admin/geo`` (blueprint lists ``.../admin/geo`` under the admin dash).",
)
def dash_admin_geo_checklist_alias(_user: AdminDashUser) -> DashAdminGeoOut:
    return _dash_admin_geo_body()
