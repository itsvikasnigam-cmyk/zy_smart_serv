from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.apps.billing_api.verify_signatures import (
    paddle_event_id,
    paddle_event_type,
    razorpay_event_id,
    razorpay_event_name,
)

logger = logging.getLogger(__name__)

VALID_ENTITLEMENT = frozenset({"trial", "starter", "growth", "pro", "churned"})


def claim_bill_event(
    conn: Connection,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str | None:
    """
    Insert a bill_events row; return its id on first insert, or None if duplicate
    (idempotent webhook replay).
    """
    row = conn.execute(
        text(
            """
            INSERT INTO bill_events (provider, provider_event_id, event_type, payload)
            VALUES (
              :provider,
              :eid,
              :etype,
              CAST(:payload AS jsonb)
            )
            ON CONFLICT (provider, provider_event_id) DO NOTHING
            RETURNING id::text
            """
        ),
        {
            "provider": provider,
            "eid": provider_event_id,
            "etype": event_type,
            "payload": json.dumps(payload),
        },
    ).fetchone()
    return row[0] if row else None


def _mark_event(conn: Connection, event_pk: str, *, applied: bool, error_message: str | None) -> None:
    conn.execute(
        text(
            """
            UPDATE bill_events
            SET applied = :applied,
                error_message = :err
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"applied": applied, "err": error_message, "id": event_pk},
    )


def _notes_dict(entity: dict[str, Any] | None) -> dict[str, str]:
    if not entity:
        return {}
    notes = entity.get("notes")
    if not isinstance(notes, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in notes.items():
        if v is None:
            continue
        out[str(k)] = str(v)
    return out


def _parse_uuid(client_id_raw: str | None) -> str | None:
    if not client_id_raw or not str(client_id_raw).strip():
        return None
    s = str(client_id_raw).strip()
    # allow with or without braces
    if len(s) == 36 and s.count("-") == 4:
        return s
    return None


def _resolve_plan_code_from_db(conn: Connection, provider: str, external_plan_id: str | None) -> str | None:
    if not external_plan_id:
        return None
    row = conn.execute(
        text(
            """
            SELECT plan_code::text
            FROM bill_plans
            WHERE provider = :provider
              AND external_plan_id = :ext
              AND active = TRUE
            LIMIT 1
            """
        ),
        {"provider": provider, "ext": external_plan_id},
    ).fetchone()
    return row[0] if row else None


def _entitlement_from_plan_code(plan_code: str | None, notes: dict[str, str]) -> str:
    raw = notes.get("entitlement_plan") or notes.get("entitlement")
    if raw and raw in VALID_ENTITLEMENT:
        return raw
    if plan_code in {"starter", "growth", "pro"}:
        return plan_code
    return "starter"


def _upsert_subscription(
    conn: Connection,
    *,
    client_id: str,
    provider: str,
    external_subscription_id: str,
    status: str,
    plan_code: str | None,
    current_period_end: Any,
    raw_payload: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO bill_subscriptions (
              client_id, provider, external_subscription_id, status,
              plan_code, current_period_end, raw_last_payload, updated_at
            )
            VALUES (
              CAST(:cid AS uuid),
              :provider,
              :ext_sub,
              :status,
              :plan_code,
              :period_end,
              CAST(:raw AS jsonb),
              now()
            )
            ON CONFLICT (provider, external_subscription_id)
            DO UPDATE SET
              client_id = EXCLUDED.client_id,
              status = EXCLUDED.status,
              plan_code = EXCLUDED.plan_code,
              current_period_end = EXCLUDED.current_period_end,
              raw_last_payload = EXCLUDED.raw_last_payload,
              updated_at = now()
            """
        ),
        {
            "cid": client_id,
            "provider": provider,
            "ext_sub": external_subscription_id,
            "status": status,
            "plan_code": plan_code,
            "period_end": current_period_end,
            "raw": json.dumps(raw_payload),
        },
    )


def _update_api_client_billing(
    conn: Connection,
    *,
    client_id: str,
    provider: str,
    entitlement_plan: str,
    billing_plan_code: str | None,
) -> int:
    res = conn.execute(
        text(
            """
            UPDATE api_clients
            SET billing_provider = :provider,
                entitlement_plan = :entitlement,
                billing_plan_code = COALESCE(:bpc, billing_plan_code)
            WHERE id = CAST(:cid AS uuid)
            """
        ),
        {
            "provider": provider,
            "entitlement": entitlement_plan,
            "bpc": billing_plan_code,
            "cid": client_id,
        },
    )
    return res.rowcount or 0


def process_razorpay_webhook(conn: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    eid = razorpay_event_id(payload)
    if not eid:
        return {"status": "ignored", "reason": "missing_event_id"}

    ev_name = razorpay_event_name(payload)
    event_row_id = claim_bill_event(
        conn,
        provider="razorpay",
        provider_event_id=eid,
        event_type=ev_name,
        payload=payload,
    )
    if not event_row_id:
        return {"status": "duplicate"}

    try:
        entity = _rz_subscription_entity(payload)
        if entity is None:
            _mark_event(conn, event_row_id, applied=True, error_message="no_subscription_payload")
            return {"status": "ignored", "reason": "no_subscription_payload"}

        notes = _notes_dict(entity)
        client_id = _parse_uuid(notes.get("client_id"))
        if not client_id:
            _mark_event(conn, event_row_id, applied=True, error_message="missing_client_id_in_notes")
            return {"status": "ignored", "reason": "missing_client_id_in_notes"}

        ext_sub = entity.get("id")
        if not isinstance(ext_sub, str) or not ext_sub.strip():
            _mark_event(conn, event_row_id, applied=True, error_message="missing_subscription_id")
            return {"status": "ignored", "reason": "missing_subscription_id"}

        plan_id = entity.get("plan_id")
        plan_code = _resolve_plan_code_from_db(conn, "razorpay", plan_id if isinstance(plan_id, str) else None)

        status = str(entity.get("status") or "unknown")
        current_end = entity.get("current_end") or entity.get("charge_at")

        if ev_name in (
            "subscription.activated",
            "subscription.charged",
            "subscription.resumed",
            "subscription.pending",
            "subscription.paused",
        ):
            entitlement = _entitlement_from_plan_code(plan_code, notes)
            bpc = notes.get("billing_plan_code") or plan_code or (str(plan_id) if plan_id else None)
            rows = _update_api_client_billing(
                conn,
                client_id=client_id,
                provider="razorpay",
                entitlement_plan=entitlement,
                billing_plan_code=bpc,
            )
            if rows == 0:
                _mark_event(conn, event_row_id, applied=True, error_message="client_not_found")
                return {"status": "ignored", "reason": "client_not_found"}

            _upsert_subscription(
                conn,
                client_id=client_id,
                provider="razorpay",
                external_subscription_id=ext_sub,
                status=status,
                plan_code=plan_code,
                current_period_end=current_end,
                raw_payload=entity,
            )
        elif ev_name in ("subscription.cancelled", "subscription.completed", "subscription.paused"):
            entitlement = "churned" if ev_name in ("subscription.cancelled", "subscription.completed") else _entitlement_from_plan_code(plan_code, notes)
            _update_api_client_billing(
                conn,
                client_id=client_id,
                provider="razorpay",
                entitlement_plan=entitlement,
                billing_plan_code=notes.get("billing_plan_code") or plan_code,
            )
            _upsert_subscription(
                conn,
                client_id=client_id,
                provider="razorpay",
                external_subscription_id=ext_sub,
                status=status,
                plan_code=plan_code,
                current_period_end=current_end,
                raw_payload=entity,
            )
        else:
            _mark_event(conn, event_row_id, applied=True, error_message=f"unhandled_event:{ev_name}")
            return {"status": "ignored", "reason": f"unhandled_event:{ev_name}"}

        _mark_event(conn, event_row_id, applied=True, error_message=None)
        return {"status": "accepted"}
    except Exception:
        logger.exception("razorpay webhook apply failed event_id=%s", eid)
        _mark_event(conn, event_row_id, applied=False, error_message="apply_exception")
        raise


def _rz_subscription_entity(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        sub = payload["payload"]["subscription"]
        ent = sub.get("entity")
        if isinstance(ent, dict):
            return ent
    except (KeyError, TypeError):
        pass
    return None


def _paddle_subscription_data(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id"):
        return data
    return None


def _paddle_custom_data(data: dict[str, Any]) -> dict[str, str]:
    cd = data.get("custom_data")
    if not isinstance(cd, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in cd.items():
        if v is None:
            continue
        out[str(k)] = str(v)
    return out


def process_paddle_webhook(conn: Connection, payload: dict[str, Any]) -> dict[str, Any]:
    eid = paddle_event_id(payload)
    if not eid:
        return {"status": "ignored", "reason": "missing_event_id"}

    ev_type = paddle_event_type(payload)
    event_row_id = claim_bill_event(
        conn,
        provider="paddle",
        provider_event_id=eid,
        event_type=ev_type,
        payload=payload,
    )
    if not event_row_id:
        return {"status": "duplicate"}

    try:
        data = _paddle_subscription_data(payload)
        if data is None:
            _mark_event(conn, event_row_id, applied=True, error_message="no_subscription_data")
            return {"status": "ignored", "reason": "no_subscription_data"}

        custom = _paddle_custom_data(data)
        client_id = _parse_uuid(custom.get("client_id"))
        if not client_id:
            _mark_event(conn, event_row_id, applied=True, error_message="missing_client_id_in_custom_data")
            return {"status": "ignored", "reason": "missing_client_id_in_custom_data"}

        ext_sub = str(data["id"])
        items = data.get("items")
        external_plan_id: str | None = None
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                price = first.get("price") or first
                if isinstance(price, dict):
                    pid = price.get("id")
                    if isinstance(pid, str):
                        external_plan_id = pid

        plan_code = _resolve_plan_code_from_db(conn, "paddle", external_plan_id)
        status = str(data.get("status") or "unknown")
        current_billing = data.get("current_billing_period") or {}
        period_ends = None
        if isinstance(current_billing, dict):
            period_ends = current_billing.get("ends_at")

        if ev_type.startswith("subscription.") and (
            "canceled" in ev_type or "cancelled" in ev_type.lower()
        ):
            entitlement = "churned"
        elif ev_type.startswith("subscription."):
            entitlement = _entitlement_from_plan_code(plan_code, custom)
        else:
            _mark_event(conn, event_row_id, applied=True, error_message=f"unhandled_event:{ev_type}")
            return {"status": "ignored", "reason": f"unhandled_event:{ev_type}"}

        bpc = custom.get("billing_plan_code") or plan_code or external_plan_id
        rows = _update_api_client_billing(
            conn,
            client_id=client_id,
            provider="paddle",
            entitlement_plan=entitlement,
            billing_plan_code=bpc,
        )
        if rows == 0:
            _mark_event(conn, event_row_id, applied=True, error_message="client_not_found")
            return {"status": "ignored", "reason": "client_not_found"}

        _upsert_subscription(
            conn,
            client_id=client_id,
            provider="paddle",
            external_subscription_id=ext_sub,
            status=status,
            plan_code=plan_code,
            current_period_end=period_ends,
            raw_payload=data,
        )

        _mark_event(conn, event_row_id, applied=True, error_message=None)
        return {"status": "accepted"}
    except Exception:
        logger.exception("paddle webhook apply failed event_id=%s", eid)
        _mark_event(conn, event_row_id, applied=False, error_message="apply_exception")
        raise
