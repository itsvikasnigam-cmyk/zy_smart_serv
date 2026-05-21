"""Chat Z: gated releases + canary policy (ops_releases + ops_runtime_config)."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("release_manager")

CANARY_POLICY_KEY = "release.canary_policy"
APPROVAL_CHECKLIST_KEY = "release.approval_checklist"

_DEFAULT_CANARY = {
    "enabled": False,
    "percent": 0,
    "active_build_id": None,
    "canary_primary_model": None,
}


@dataclass(frozen=True)
class CanaryPolicy:
    enabled: bool
    percent: int
    active_build_id: str | None
    canary_primary_model: str | None


def merge_canary_policy(value_json: Any | None) -> dict[str, Any]:
    out = dict(_DEFAULT_CANARY)
    if isinstance(value_json, dict):
        for k, v in value_json.items():
            if k in out:
                out[k] = v
    return out


def _coerce_percent(raw: Any) -> int:
    try:
        p = int(raw)
    except (TypeError, ValueError):
        p = 0
    return max(0, min(p, 100))


def load_canary_policy_conn(conn: Connection) -> CanaryPolicy:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
        {"k": CANARY_POLICY_KEY},
    ).fetchone()
    merged = merge_canary_policy(row[0] if row else None)
    bid = merged.get("active_build_id")
    model = merged.get("canary_primary_model")
    return CanaryPolicy(
        enabled=bool(merged.get("enabled")),
        percent=_coerce_percent(merged.get("percent")),
        active_build_id=str(bid).strip() if bid else None,
        canary_primary_model=str(model).strip() if model else None,
    )


def load_canary_policy_engine(engine: Engine) -> CanaryPolicy:
    with engine.connect() as conn:
        return load_canary_policy_conn(conn)


def save_canary_policy_conn(
    conn: Connection,
    *,
    enabled: bool | None = None,
    percent: int | None = None,
    active_build_id: str | None = None,
    canary_primary_model: str | None = None,
) -> CanaryPolicy:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k LIMIT 1"),
        {"k": CANARY_POLICY_KEY},
    ).fetchone()
    merged = merge_canary_policy(row[0] if row else None)
    if enabled is not None:
        merged["enabled"] = enabled
    if percent is not None:
        merged["percent"] = _coerce_percent(percent)
    if active_build_id is not None:
        merged["active_build_id"] = active_build_id.strip() or None
    if canary_primary_model is not None:
        merged["canary_primary_model"] = canary_primary_model.strip() or None
    conn.execute(
        text(
            """
            INSERT INTO ops_runtime_config (key, value_json)
            VALUES (:k, CAST(:v AS jsonb))
            ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
            """
        ),
        {"k": CANARY_POLICY_KEY, "v": json.dumps(merged)},
    )
    return policy_from_merged(merged)


def policy_from_merged(merged: dict[str, Any]) -> CanaryPolicy:
    bid = merged.get("active_build_id")
    model = merged.get("canary_primary_model")
    return CanaryPolicy(
        enabled=bool(merged.get("enabled")),
        percent=_coerce_percent(merged.get("percent")),
        active_build_id=str(bid).strip() if bid else None,
        canary_primary_model=str(model).strip() if model else None,
    )


def disable_canary_quick(conn: Connection, *, note: str | None = None) -> CanaryPolicy:
    """Turn off canary immediately (acceptance: disable quickly)."""
    policy = save_canary_policy_conn(conn, enabled=False, percent=0)
    log.warning("canary disabled (quick): %s", note or "")
    return policy


def should_route_chat_to_canary(chat_id: str, policy: CanaryPolicy | None = None) -> bool:
    if policy is None:
        return False
    if not policy.enabled or policy.percent <= 0:
        return False
    digest = hashlib.sha256(chat_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < policy.percent


def _record_event(
    conn: Connection,
    *,
    release_id: str,
    action: str,
    actor_user_id: str | None,
    note: str | None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO ops_release_events (release_id, action, actor_user_id, note)
            VALUES (CAST(:rid AS uuid), :act, CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END, :note)
            """
        ),
        {
            "rid": release_id,
            "act": action,
            "uid": actor_user_id or "",
            "note": (note or "")[:2000] or None,
        },
    )


def register_release(
    conn: Connection,
    *,
    build_id: str,
    git_sha: str | None = None,
    artifact_hash: str | None = None,
    test_report_hash: str | None = None,
    notes: str | None = None,
    actor_user_id: str | None = None,
) -> str:
    bid = build_id.strip()
    if not bid:
        raise ValueError("build_id required")
    try:
        row = conn.execute(
            text(
                """
                INSERT INTO ops_releases (
                  build_id, git_sha, status, artifact_hash, test_report_hash, notes, registered_by_user_id
                )
                VALUES (
                  :bid, :sha, 'candidate', :art, :test, :notes,
                  CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END
                )
                RETURNING id::text
                """
            ),
            {
                "bid": bid,
                "sha": (git_sha or "").strip() or None,
                "art": (artifact_hash or "").strip() or None,
                "test": (test_report_hash or "").strip() or None,
                "notes": (notes or "").strip() or None,
                "uid": actor_user_id or "",
            },
        ).fetchone()
    except IntegrityError as exc:
        raise ValueError(f"build_id already registered: {bid}") from exc
    if not row:
        raise RuntimeError("register_release failed")
    rid = str(row[0])
    _record_event(conn, release_id=rid, action="registered", actor_user_id=actor_user_id, note=notes)
    return rid


def promote_release(
    conn: Connection,
    *,
    build_id: str,
    actor_user_id: str | None = None,
    canary_percent: int = 0,
    canary_primary_model: str | None = None,
    note: str | None = None,
) -> str:
    bid = build_id.strip()
    row = conn.execute(
        text(
            """
            SELECT id::text, status FROM ops_releases WHERE build_id = :bid LIMIT 1
            """
        ),
        {"bid": bid},
    ).fetchone()
    if not row:
        raise ValueError(f"unknown build_id: {bid}")
    rid, st = str(row[0]), str(row[1])
    if st == "rolled_back":
        raise ValueError(f"cannot promote rolled_back build: {bid}")

    conn.execute(
        text(
            """
            UPDATE ops_releases
            SET status = 'candidate'
            WHERE status = 'promoted'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE ops_releases
            SET status = 'promoted',
                promoted_at = now(),
                promoted_by_user_id = CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END
            WHERE id = CAST(:rid AS uuid)
            """
        ),
        {"rid": rid, "uid": actor_user_id or ""},
    )
    _record_event(conn, release_id=rid, action="promoted", actor_user_id=actor_user_id, note=note)

    save_canary_policy_conn(
        conn,
        enabled=canary_percent > 0,
        percent=canary_percent,
        active_build_id=bid,
        canary_primary_model=canary_primary_model,
    )
    return rid


def rollback_release(
    conn: Connection,
    *,
    build_id: str,
    actor_user_id: str | None = None,
    note: str | None = None,
) -> str:
    bid = build_id.strip()
    row = conn.execute(
        text("SELECT id::text FROM ops_releases WHERE build_id = :bid LIMIT 1"),
        {"bid": bid},
    ).fetchone()
    if not row:
        raise ValueError(f"unknown build_id: {bid}")
    rid = str(row[0])
    conn.execute(
        text(
            """
            UPDATE ops_releases
            SET status = 'rolled_back',
                rolled_back_at = now(),
                rolled_back_by_user_id = CASE WHEN :uid = '' THEN NULL ELSE CAST(:uid AS uuid) END
            WHERE id = CAST(:rid AS uuid)
            """
        ),
        {"rid": rid, "uid": actor_user_id or ""},
    )
    _record_event(conn, release_id=rid, action="rolled_back", actor_user_id=actor_user_id, note=note)
    disable_canary_quick(conn, note=f"rollback {bid}")
    _record_event(conn, release_id=rid, action="canary_disabled", actor_user_id=actor_user_id, note="rollback hook")
    return rid


def get_promoted_build_id(conn: Connection) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT build_id FROM ops_releases
            WHERE status = 'promoted'
            ORDER BY promoted_at DESC NULLS LAST
            LIMIT 1
            """
        )
    ).fetchone()
    return str(row[0]) if row else None
