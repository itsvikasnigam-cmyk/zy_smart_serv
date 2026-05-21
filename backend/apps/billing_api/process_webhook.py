from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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


def _coerce_timestamptz(value: Any) -> datetime | None:
    """Razorpay often sends Unix seconds; Paddle sends ISO strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        s = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


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


def _rz_nested_entity(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    try:
        wrap = payload["payload"][key]
        ent = wrap.get("entity") if isinstance(wrap, dict) else None
        return ent if isinstance(ent, dict) else None
    except (KeyError, TypeError):
        return None


def _resolve_rz_client_from_payment(conn: Connection, ent: dict[str, Any]) -> str | None:
    notes = _notes_dict(ent)
    cid = _parse_uuid(notes.get("client_id"))
    if cid:
        return cid
    sub_id = ent.get("subscription_id")
    if isinstance(sub_id, str) and sub_id.strip():
        row = conn.execute(
            text(
                """
                SELECT client_id::text
                FROM bill_subscriptions
                WHERE provider = 'razorpay' AND external_subscription_id = :sid
                LIMIT 1
                """
            ),
            {"sid": sub_id.strip()},
        ).fetchone()
        if row and row[0]:
            return str(row[0])
    return None


def upsert_bill_invoice(
    conn: Connection,
    *,
    client_id: str,
    provider: str,
    external_invoice_id: str,
    amount_minor: int | None,
    currency: str | None,
    status: str,
    issued_at: Any,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO bill_invoices (
              client_id, provider, external_invoice_id, amount_minor, currency, status, issued_at, payload
            )
            VALUES (
              CAST(:cid AS uuid),
              :provider,
              :eid,
              :amt,
              :cur,
              :st,
              :issued,
              CAST(:payload AS jsonb)
            )
            ON CONFLICT (provider, external_invoice_id)
            DO UPDATE SET
              client_id = EXCLUDED.client_id,
              amount_minor = COALESCE(EXCLUDED.amount_minor, bill_invoices.amount_minor),
              currency = COALESCE(EXCLUDED.currency, bill_invoices.currency),
              status = EXCLUDED.status,
              issued_at = COALESCE(EXCLUDED.issued_at, bill_invoices.issued_at),
              payload = EXCLUDED.payload
            """
        ),
        {
            "cid": client_id,
            "provider": provider,
            "eid": external_invoice_id,
            "amt": amount_minor,
            "cur": currency,
            "st": status,
            "issued": issued_at,
            "payload": json.dumps(payload),
        },
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
        # --- Invoice paid (renewal / charge receipt) ---
        if ev_name == "invoice.paid":
            inv = _rz_nested_entity(payload, "invoice")
            if inv is None:
                _mark_event(conn, event_row_id, applied=True, error_message="no_invoice_payload")
                return {"status": "ignored", "reason": "no_invoice_payload"}
            notes_i = _notes_dict(inv)
            client_id_i = _parse_uuid(notes_i.get("client_id"))
            if not client_id_i:
                _mark_event(conn, event_row_id, applied=True, error_message="missing_client_id_invoice")
                return {"status": "ignored", "reason": "missing_client_id_in_notes"}
            inv_id = inv.get("id")
            if not isinstance(inv_id, str) or not inv_id.strip():
                _mark_event(conn, event_row_id, applied=True, error_message="missing_invoice_id")
                return {"status": "ignored", "reason": "missing_invoice_id"}
            amt_raw = inv.get("amount")
            try:
                amt_i = int(amt_raw) if amt_raw is not None else None
            except (TypeError, ValueError):
                amt_i = None
            cur = inv.get("currency")
            upsert_bill_invoice(
                conn,
                client_id=client_id_i,
                provider="razorpay",
                external_invoice_id=inv_id.strip(),
                amount_minor=amt_i,
                currency=str(cur) if cur else None,
                status="paid",
                issued_at=_coerce_timestamptz(inv.get("paid_at") or inv.get("created_at")),
                payload=inv,
            )
            _mark_event(conn, event_row_id, applied=True, error_message=None)
            return {"status": "accepted"}

        # --- Payment failure ---
        if ev_name == "payment.failed":
            pay = _rz_nested_entity(payload, "payment")
            if pay is None:
                _mark_event(conn, event_row_id, applied=True, error_message="no_payment_payload")
                return {"status": "ignored", "reason": "no_payment_payload"}
            cidp = _resolve_rz_client_from_payment(conn, pay)
            if not cidp:
                _mark_event(conn, event_row_id, applied=True, error_message="missing_client_payment")
                return {"status": "ignored", "reason": "missing_client_id"}
            _update_api_client_billing(
                conn,
                client_id=cidp,
                provider="razorpay",
                entitlement_plan="churned",
                billing_plan_code=None,
            )
            sub_id = pay.get("subscription_id")
            if isinstance(sub_id, str) and sub_id.strip():
                conn.execute(
                    text(
                        """
                        UPDATE bill_subscriptions
                        SET status = 'payment_failed', updated_at = now(),
                            raw_last_payload = CAST(:p AS jsonb)
                        WHERE provider = 'razorpay' AND external_subscription_id = :sid
                        """
                    ),
                    {"sid": sub_id.strip(), "p": json.dumps(pay)},
                )
            _mark_event(conn, event_row_id, applied=True, error_message=None)
            return {"status": "accepted"}

        # --- Refund processed ---
        if ev_name == "refund.processed":
            ref = _rz_nested_entity(payload, "refund")
            if ref is None:
                _mark_event(conn, event_row_id, applied=True, error_message="no_refund_payload")
                return {"status": "ignored", "reason": "no_refund_payload"}
            notes_r = _notes_dict(ref)
            cid_r = _parse_uuid(notes_r.get("client_id"))
            if not cid_r:
                _mark_event(conn, event_row_id, applied=True, error_message="missing_client_refund")
                return {"status": "ignored", "reason": "missing_client_id_in_notes"}
            rid = ref.get("id")
            if isinstance(rid, str) and rid.strip():
                try:
                    amt_r = int(ref.get("amount")) if ref.get("amount") is not None else None
                except (TypeError, ValueError):
                    amt_r = None
                upsert_bill_invoice(
                    conn,
                    client_id=cid_r,
                    provider="razorpay",
                    external_invoice_id=f"refund:{rid.strip()}",
                    amount_minor=amt_r,
                    currency=str(ref.get("currency") or "INR"),
                    status="refunded",
                    issued_at=_coerce_timestamptz(ref.get("created_at")),
                    payload=ref,
                )
            _update_api_client_billing(
                conn,
                client_id=cid_r,
                provider="razorpay",
                entitlement_plan="churned",
                billing_plan_code=None,
            )
            _mark_event(conn, event_row_id, applied=True, error_message=None)
            return {"status": "accepted"}

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
        current_end = _coerce_timestamptz(entity.get("current_end") or entity.get("charge_at"))

        if ev_name in (
            "subscription.activated",
            "subscription.charged",
            "subscription.resumed",
            "subscription.pending",
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
        elif ev_name in ("subscription.cancelled", "subscription.completed", "subscription.halted"):
            entitlement = "churned"
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
        elif ev_name == "subscription.paused":
            entitlement = _entitlement_from_plan_code(plan_code, notes)
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
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            _mark_event(conn, event_row_id, applied=True, error_message="no_event_data")
            return {"status": "ignored", "reason": "no_event_data"}

        custom = _paddle_custom_data(data)
        client_id = _parse_uuid(custom.get("client_id"))

        # --- Paddle Billing: transactions (failures / paid receipts) ---
        if ev_type.startswith("transaction."):
            if not client_id:
                _mark_event(conn, event_row_id, applied=True, error_message="missing_client_id_in_custom_data")
                return {"status": "ignored", "reason": "missing_client_id_in_custom_data"}
            tid = str(data["id"])
            st = str(data.get("status") or "").lower()
            if "payment_failed" in ev_type or st == "failed":
                _update_api_client_billing(
                    conn,
                    client_id=client_id,
                    provider="paddle",
                    entitlement_plan="churned",
                    billing_plan_code=None,
                )
                upsert_bill_invoice(
                    conn,
                    client_id=client_id,
                    provider="paddle",
                    external_invoice_id=tid,
                    amount_minor=None,
                    currency=None,
                    status="failed",
                    issued_at=_coerce_timestamptz(data.get("created_at") or data.get("updated_at")),
                    payload=data,
                )
                _mark_event(conn, event_row_id, applied=True, error_message=None)
                return {"status": "accepted"}
            if "paid" in ev_type or st in ("paid", "completed") or "completed" in ev_type.lower():
                upsert_bill_invoice(
                    conn,
                    client_id=client_id,
                    provider="paddle",
                    external_invoice_id=tid,
                    amount_minor=None,
                    currency=None,
                    status="paid",
                    issued_at=_coerce_timestamptz(data.get("created_at") or data.get("updated_at")),
                    payload=data,
                )
                _mark_event(conn, event_row_id, applied=True, error_message=None)
                return {"status": "accepted"}
            _mark_event(conn, event_row_id, applied=True, error_message=f"unhandled_transaction:{ev_type}")
            return {"status": "ignored", "reason": f"unhandled_transaction:{ev_type}"}

        # --- Refunds ---
        if ev_type.startswith("refund."):
            if not client_id:
                _mark_event(conn, event_row_id, applied=True, error_message="missing_client_id_in_custom_data")
                return {"status": "ignored", "reason": "missing_client_id_in_custom_data"}
            rid = str(data["id"])
            upsert_bill_invoice(
                conn,
                client_id=client_id,
                provider="paddle",
                external_invoice_id=f"refund:{rid}",
                amount_minor=None,
                currency=None,
                status="refunded",
                issued_at=_coerce_timestamptz(data.get("created_at")),
                payload=data,
            )
            _update_api_client_billing(
                conn,
                client_id=client_id,
                provider="paddle",
                entitlement_plan="churned",
                billing_plan_code=None,
            )
            _mark_event(conn, event_row_id, applied=True, error_message=None)
            return {"status": "accepted"}

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
            period_ends = _coerce_timestamptz(current_billing.get("ends_at"))

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
