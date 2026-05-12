from __future__ import annotations

import os
import socket
import time
from typing import Any

import httpx
from sqlalchemy import text

from backend.shared.config import settings
from backend.shared.db import engine


INSTANCE_ID = os.environ.get("INSTANCE_ID") or socket.gethostname()


class MetaSendRetryable(Exception):
    """Transient Meta / network failure — backoff and retry."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class MetaSendFatal(Exception):
    """Non-recoverable send error (e.g. bad token) — mark DEAD without burning many attempts."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _meta_error_summary(response: httpx.Response) -> tuple[int | None, str]:
    try:
        data: dict[str, Any] = response.json()
        err = data.get("error") or {}
        code = err.get("code")
        sub = err.get("error_subcode")
        msg = err.get("message", "")
        fbtrace = err.get("fbtrace_id", "")
        parts = [f"code={code}", f"subcode={sub}", msg, f"fbtrace_id={fbtrace}" if fbtrace else ""]
        return int(code) if code is not None else None, " | ".join(p for p in parts if p)
    except Exception:
        return None, (response.text or "")[:2000]


def _meta_send(phone_number_id: str, to_phone: str, body: str) -> str:
    url = f"https://graph.facebook.com/{settings.meta_graph_version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.meta_access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "text", "text": {"body": body}}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(url, headers=headers, json=payload)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
        raise MetaSendRetryable(f"{type(e).__name__}: {e}") from e

    if r.status_code == 401:
        _, detail = _meta_error_summary(r)
        raise MetaSendFatal(f"HTTP 401 unauthorized ({detail})") from None
    if r.status_code == 403:
        _, detail = _meta_error_summary(r)
        raise MetaSendFatal(f"HTTP 403 forbidden ({detail})") from None
    if r.status_code == 429:
        raise MetaSendRetryable(f"HTTP 429 rate limited: {_meta_error_summary(r)[1]}") from None
    if r.status_code >= 500:
        raise MetaSendRetryable(f"HTTP {r.status_code} server error: {_meta_error_summary(r)[1]}") from None

    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        _, detail = _meta_error_summary(r)
        # Most 4xx from Graph are misconfiguration or bad recipient — do not spin forever.
        if r.status_code >= 400:
            raise MetaSendFatal(f"HTTP {r.status_code} ({detail})") from e

    try:
        data = r.json()
    except Exception as e:
        raise MetaSendRetryable(f"meta send: invalid json: {e}") from e

    msg_id = None
    for m in data.get("messages") or []:
        if m.get("id"):
            msg_id = m["id"]
            break
    if not msg_id:
        raise MetaSendRetryable(f"meta send: missing message id in response: {repr(data)[:800]}")
    return str(msg_id)


def _claim_one_outbox_row() -> tuple[Any, ...] | None:
    """Atomically pick one due row and mark SENDING with a lease on next_attempt_at."""
    lease = int(settings.outbox_sending_lease_seconds)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                WITH picked AS (
                  SELECT
                    o.id,
                    o.from_wa_number_id,
                    o.to_phone_e164,
                    o.body_text,
                    o.attempt_count,
                    o.status AS prior_status
                  FROM wa_outbox o
                  WHERE (
                      (o.status IN ('PENDING', 'FAILED') AND o.next_attempt_at <= now())
                      OR (o.status = 'SENDING' AND o.next_attempt_at <= now())
                    )
                  ORDER BY o.next_attempt_at ASC
                  FOR UPDATE SKIP LOCKED
                  LIMIT 1
                )
                UPDATE wa_outbox o
                SET
                  status = 'SENDING',
                  next_attempt_at = now() + (:lease_sec || ' seconds')::interval,
                  attempt_count = CASE WHEN p.prior_status = 'SENDING' THEN o.attempt_count + 1 ELSE o.attempt_count END
                FROM picked p
                LEFT JOIN wa_numbers w ON w.id = p.from_wa_number_id
                WHERE o.id = p.id
                RETURNING
                  o.id,
                  o.to_phone_e164,
                  o.body_text,
                  o.attempt_count,
                  w.meta_phone_number_id
                """
            ),
            {"lease_sec": lease},
        ).fetchone()
    return row


def _finalize_sent(outbox_id: Any, meta_message_id: str) -> bool:
    """Mark SENT only if still SENDING (idempotent if another worker already finished)."""
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                UPDATE wa_outbox
                SET status = 'SENT',
                    meta_message_id = :mid,
                    sent_at = now(),
                    last_error_code = NULL,
                    last_error_detail = NULL
                WHERE id = CAST(:id AS uuid) AND status = 'SENDING'
                RETURNING id
                """
            ),
            {"id": str(outbox_id), "mid": meta_message_id},
        ).fetchone()
    return bool(res)


def _finalize_failure_or_dead(outbox_id: Any, *, error_code: str, error_detail: str, fatal: bool) -> None:
    max_a = int(settings.outbox_max_attempts)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE wa_outbox
                SET attempt_count = attempt_count + 1
                WHERE id = CAST(:id AS uuid) AND status = 'SENDING'
                RETURNING attempt_count
                """
            ),
            {"id": str(outbox_id)},
        ).fetchone()
        if not row:
            return
        new_count = int(row[0])
        if fatal or new_count >= max_a:
            conn.execute(
                text(
                    """
                    UPDATE wa_outbox
                    SET status = 'DEAD',
                        last_error_code = :code,
                        last_error_detail = :detail
                    WHERE id = CAST(:id AS uuid) AND status = 'SENDING'
                    """
                ),
                {
                    "id": str(outbox_id),
                    "code": "DEAD" if new_count >= max_a else error_code,
                    "detail": error_detail[:8000],
                },
            )
            return
        next_seconds = min(300, 5 * new_count)
        conn.execute(
            text(
                """
                UPDATE wa_outbox
                SET status = 'FAILED',
                    next_attempt_at = now() + (:s || ' seconds')::interval,
                    last_error_code = :code,
                    last_error_detail = :detail
                WHERE id = CAST(:id AS uuid) AND status = 'SENDING'
                """
            ),
            {"id": str(outbox_id), "s": next_seconds, "code": error_code, "detail": error_detail[:8000]},
        )


def _finalize_missing_token(outbox_id: Any) -> None:
    detail = "META_ACCESS_TOKEN not configured (set env META_ACCESS_TOKEN for outbox_sender)"
    _finalize_failure_or_dead(outbox_id, error_code="NO_ACCESS_TOKEN", error_detail=detail, fatal=False)


def _finalize_missing_phone_row(outbox_id: Any) -> None:
    _finalize_failure_or_dead(
        outbox_id,
        error_code="WA_NUMBER_CONFIG",
        error_detail="wa_numbers.meta_phone_number_id missing for from_wa_number_id",
        fatal=True,
    )


def run_once() -> int:
    """
    Send up to 25 outbox messages per wake (short DB transactions around Meta HTTP).

    States: PENDING/FAILED (due) or expired SENDING lease → claim as SENDING with lease on
    next_attempt_at. Success → SENT + meta_message_id. Failure → FAILED with backoff or DEAD
    when attempt_count reaches outbox_max_attempts. Fatal Meta errors → DEAD immediately after
    increment when over max, or on first fatal depending on path.

    Note: If the process dies after Meta returns 200 but before the SENT update commits, a
    lease expiry may cause a resend (WhatsApp Cloud API has no application idempotency key here).
    Keep leases reasonably long and commit SENT immediately after JSON parse.
    """
    sent_ok = 0
    claimed_any = False
    max_per_tick = 25
    for _ in range(max_per_tick):
        row = _claim_one_outbox_row()
        if not row:
            break
        claimed_any = True
        outbox_id, to_phone, body_text, _attempt_after_claim, phone_number_id = row

        if not settings.meta_access_token:
            _finalize_missing_token(outbox_id)
            continue
        if not phone_number_id:
            _finalize_missing_phone_row(outbox_id)
            continue

        try:
            meta_message_id = _meta_send(str(phone_number_id), str(to_phone), str(body_text))
        except MetaSendFatal as e:
            _finalize_failure_or_dead(
                outbox_id,
                error_code="META_FATAL",
                error_detail=f"{e.detail} ({INSTANCE_ID})",
                fatal=True,
            )
            continue
        except MetaSendRetryable as e:
            _finalize_failure_or_dead(
                outbox_id,
                error_code="META_RETRYABLE",
                error_detail=f"{e.detail} ({INSTANCE_ID})",
                fatal=False,
            )
            continue
        except Exception as e:
            _finalize_failure_or_dead(
                outbox_id,
                error_code="SEND_FAILED",
                error_detail=f"{type(e).__name__}: {e} ({INSTANCE_ID})",
                fatal=False,
            )
            continue

        if _finalize_sent(outbox_id, meta_message_id):
            sent_ok += 1

    # Keep main() snappy when only failures occurred (still avoid hot-spin on empty queue).
    return sent_ok if sent_ok > 0 else (1 if claimed_any else 0)


def main() -> None:
    while True:
        try:
            n = run_once()
            time.sleep(0.25 if n > 0 else 1.0)
        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    main()
