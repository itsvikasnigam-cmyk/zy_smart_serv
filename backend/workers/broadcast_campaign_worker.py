"""
M6: process ``wa_broadcast_campaigns`` / ``wa_broadcast_targets`` into ``wa_outbox`` TEMPLATE rows.

Enforces ``m6.broadcast_policy`` (trial/starter block matrix + opt-in) and template-only JSON bodies.
Run alongside other workers (see HANDOFF).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.broadcast_gating import (
    M6_POLICY_KEY,
    build_template_outbox_body,
    merge_m6_policy,
    plan_allows_broadcast,
    validate_template_only_body,
)
from backend.shared.config import settings
from backend.shared.db import engine

log = logging.getLogger("broadcast_campaign_worker")


def _load_m6_policy(conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": M6_POLICY_KEY},
    ).fetchone()
    return merge_m6_policy(row[0] if row else None)


def _pick_queued_campaign(conn: Connection) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            WITH c AS (
              SELECT id FROM wa_broadcast_campaigns
              WHERE status = 'queued'
              ORDER BY created_at ASC
              FOR UPDATE SKIP LOCKED
              LIMIT 1
            )
            UPDATE wa_broadcast_campaigns w
            SET status = 'running', started_at = COALESCE(w.started_at, now())
            FROM c
            WHERE w.id = c.id
            RETURNING
              w.id, w.client_id, w.from_wa_number_id, w.template_name, w.template_language
            """
        )
    ).fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "client_id": str(row[1]),
        "from_wa_number_id": str(row[2]),
        "template_name": str(row[3]),
        "template_language": str(row[4] or "en_US"),
    }


def _maybe_finish_campaign(conn: Connection, campaign_id: str) -> None:
    pending = conn.execute(
        text(
            """
            SELECT 1 FROM wa_broadcast_targets
            WHERE campaign_id = CAST(:cid AS uuid) AND status = 'pending'
            LIMIT 1
            """
        ),
        {"cid": campaign_id},
    ).fetchone()
    if pending:
        return
    conn.execute(
        text(
            """
            UPDATE wa_broadcast_campaigns
            SET status = 'completed', finished_at = now(), error_message = NULL
            WHERE id = CAST(:cid AS uuid) AND status = 'running'
            """
        ),
        {"cid": campaign_id},
    )


def _process_one_target(
    conn: Connection,
    *,
    campaign: dict[str, Any],
    policy: dict[str, Any],
    target_id: str,
    chat_id: str,
    phone: str,
) -> None:
    cid = campaign["client_id"]
    ent_row = conn.execute(
        text("SELECT entitlement_plan FROM api_clients WHERE id = CAST(:id AS uuid)"),
        {"id": cid},
    ).fetchone()
    entitlement = str(ent_row[0]) if ent_row and ent_row[0] is not None else ""

    if not plan_allows_broadcast(entitlement, policy):
        conn.execute(
            text(
                """
                UPDATE wa_broadcast_targets
                SET status = 'skipped_plan', skip_detail = :sd, updated_at = now()
                WHERE id = CAST(:tid AS uuid)
                """
            ),
            {"tid": target_id, "sd": f"plan={entitlement} blocked by {M6_POLICY_KEY}"},
        )
        return

    require_opt = bool(policy.get("require_marketing_opt_in", True))
    opted_in = False
    if require_opt:
        oi = conn.execute(
            text(
                """
                SELECT opted_in FROM customer_marketing_opt_in
                WHERE client_id = CAST(:cid AS uuid) AND customer_phone_e164 = :phone
                """
            ),
            {"cid": cid, "phone": phone},
        ).fetchone()
        opted_in = bool(oi and oi[0])
    else:
        opted_in = True

    if not opted_in:
        conn.execute(
            text(
                """
                UPDATE wa_broadcast_targets
                SET status = 'skipped_no_optin', skip_detail = 'require_marketing_opt_in', updated_at = now()
                WHERE id = CAST(:tid AS uuid)
                """
            ),
            {"tid": target_id},
        )
        return

    template_only = bool(policy.get("template_only", True))
    body = build_template_outbox_body(
        template_name=campaign["template_name"],
        language=campaign["template_language"],
        components=[],
    )
    ok, err = validate_template_only_body(body, template_only=template_only)
    if not ok:
        conn.execute(
            text(
                """
                UPDATE wa_broadcast_targets
                SET status = 'skipped_template_policy', skip_detail = :sd, updated_at = now()
                WHERE id = CAST(:tid AS uuid)
                """
            ),
            {"tid": target_id, "sd": err[:2000]},
        )
        return

    idem = f"broadcast:{campaign['id']}:{chat_id}"
    row = conn.execute(
        text(
            """
            INSERT INTO wa_outbox(
              client_id, chat_id, to_phone_e164, from_wa_number_id,
              kind, body_text, reply_to_batch_id, idempotency_key, status
            )
            VALUES (
              CAST(:client_id AS uuid), CAST(:chat_id AS uuid), :phone, CAST(:from_wa AS uuid),
              'TEMPLATE', :body, NULL, :idem, 'PENDING'
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "client_id": cid,
            "chat_id": chat_id,
            "phone": phone,
            "from_wa": campaign["from_wa_number_id"],
            "body": body,
            "idem": idem,
        },
    ).fetchone()
    if not row:
        existing = conn.execute(
            text("SELECT id FROM wa_outbox WHERE idempotency_key = :idem LIMIT 1"),
            {"idem": idem},
        ).fetchone()
        oid = str(existing[0]) if existing else None
        if oid:
            conn.execute(
                text(
                    """
                    UPDATE wa_broadcast_targets
                    SET status = 'enqueued',
                        wa_outbox_id = CAST(:oid AS uuid),
                        skip_detail = 'duplicate idempotency',
                        updated_at = now()
                    WHERE id = CAST(:tid AS uuid)
                    """
                ),
                {"tid": target_id, "oid": oid},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE wa_broadcast_targets
                    SET status = 'failed',
                        skip_detail = 'outbox insert failed',
                        updated_at = now()
                    WHERE id = CAST(:tid AS uuid)
                    """
                ),
                {"tid": target_id},
            )
        return
    oid = str(row[0])
    conn.execute(
        text(
            """
            UPDATE wa_broadcast_targets
            SET status = 'enqueued', wa_outbox_id = CAST(:oid AS uuid), updated_at = now()
            WHERE id = CAST(:tid AS uuid)
            """
        ),
        {"tid": target_id, "oid": oid},
    )


def run_once() -> int:
    """Returns number of targets transitioned (skip or enqueue) this tick."""
    n = 0
    batch = int(settings.broadcast_worker_batch_size)
    with engine.begin() as conn:
        policy = _load_m6_policy(conn)
        campaign = _pick_queued_campaign(conn)
        if not campaign:
            return 0
        cid = campaign["id"]
        targets = conn.execute(
            text(
                """
                SELECT id, chat_id, customer_phone_e164
                FROM wa_broadcast_targets
                WHERE campaign_id = CAST(:cid AS uuid) AND status = 'pending'
                ORDER BY id ASC
                LIMIT :lim
                FOR UPDATE SKIP LOCKED
                """
            ),
            {"cid": cid, "lim": batch},
        ).fetchall()
        if not targets:
            _maybe_finish_campaign(conn, cid)
            return 0
        for tid, chat_id, phone in targets:
            _process_one_target(
                conn,
                campaign=campaign,
                policy=policy,
                target_id=str(tid),
                chat_id=str(chat_id),
                phone=str(phone),
            )
            n += 1
        _maybe_finish_campaign(conn, cid)
    return n


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("broadcast_campaign_worker started (interval=%ss)", settings.broadcast_worker_sleep_seconds)
    while True:
        try:
            processed = run_once()
            if processed:
                log.info("broadcast targets processed=%s", processed)
        except Exception:
            log.exception("broadcast_campaign_worker tick error")
        time.sleep(settings.broadcast_worker_sleep_seconds)


if __name__ == "__main__":
    main()
