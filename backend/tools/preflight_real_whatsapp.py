"""Preflight checks before a real WhatsApp send test.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend\\tools\\preflight_real_whatsapp.py

This tool does not print secrets.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.config import settings
from backend.shared.db import engine
from backend.shared.wa_service_window import POLICY_KEY, merge_service_window_policy

EXPECTED_META_PHONE_NUMBER_ID = "1098044196727032"


def _ok(label: str, detail: str = "") -> bool:
    print(f"OK   {label}{(': ' + detail) if detail else ''}")
    return True


def _warn(label: str, detail: str = "") -> bool:
    print(f"WARN {label}{(': ' + detail) if detail else ''}")
    return True


def _fail(label: str, detail: str = "") -> bool:
    print(f"FAIL {label}{(': ' + detail) if detail else ''}")
    return False


def _fingerprint(token: str) -> str:
    t = (token or "").strip()
    if not t:
        return "(empty)"
    if len(t) < 12:
        return f"len={len(t)}"
    return f"len={len(t)} start={t[:8]}...end={t[-4:]}"


def _env_file_token() -> tuple[str, int]:
    env_path = _root / "backend" / ".env"
    if not env_path.exists():
        return "", 0
    token = ""
    count = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("META_ACCESS_TOKEN="):
            count += 1
            token = s.split("=", 1)[1].strip().strip('"').strip("'")
    return token, count


def check_env_token() -> bool:
    file_token, count = _env_file_token()
    proc_token = (os.environ.get("META_ACCESS_TOKEN") or "").strip()
    loaded = (settings.meta_access_token or "").strip()

    good = True
    if count != 1:
        good = _fail("backend/.env META_ACCESS_TOKEN line count", str(count))
    else:
        _ok("backend/.env META_ACCESS_TOKEN present", _fingerprint(file_token))

    if proc_token and proc_token != file_token:
        good = _fail("Windows/process META_ACCESS_TOKEN overrides backend/.env", _fingerprint(proc_token))
    elif proc_token:
        _ok("process META_ACCESS_TOKEN matches backend/.env", _fingerprint(proc_token))
    else:
        _ok("process META_ACCESS_TOKEN not set", "backend/.env is source of truth")

    if loaded != file_token:
        good = _fail("settings META_ACCESS_TOKEN differs from backend/.env", _fingerprint(loaded))
    else:
        _ok("settings META_ACCESS_TOKEN matches backend/.env", _fingerprint(loaded))
    return good


def check_meta_token() -> bool:
    token = (settings.meta_access_token or "").strip()
    if not token:
        return _fail("Meta token", "empty")
    url = (
        f"https://graph.facebook.com/{settings.meta_graph_version}/{EXPECTED_META_PHONE_NUMBER_ID}"
        "?fields=id,display_phone_number,verified_name"
    )
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20.0)
    except Exception as e:
        return _fail("Meta token request", f"{type(e).__name__}: {e}")
    if r.status_code == 200:
        return _ok("Meta token can access phone_number_id", r.text[:300])
    return _fail("Meta token rejected", f"HTTP {r.status_code}: {r.text[:500]}")


def check_http(name: str, url: str, must_contain: str | None = None) -> bool:
    try:
        r = httpx.get(url, timeout=5.0)
    except Exception as e:
        return _fail(name, f"{type(e).__name__}: {e}")
    body = r.text[:600]
    if r.status_code != 200:
        return _fail(name, f"HTTP {r.status_code}: {body}")
    if must_contain and must_contain not in body:
        return _fail(name, f"missing {must_contain!r}: {body}")
    return _ok(name, body)


def check_db() -> bool:
    good = True
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        if not rev:
            good = _fail("alembic_version", "missing")
        else:
            _ok("alembic current", str(rev))

        rows = conn.execute(
            text(
                """
                SELECT phone_e164, meta_phone_number_id, status
                FROM wa_numbers
                ORDER BY created_at ASC
                """
            )
        ).all()
        if not rows:
            good = _fail("wa_numbers", "no rows")
        else:
            found = False
            for phone, meta_id, status in rows:
                detail = f"phone={phone} meta_phone_number_id={meta_id} status={status}"
                if str(meta_id) == EXPECTED_META_PHONE_NUMBER_ID:
                    found = True
                    _ok("wa_numbers routing", detail)
                else:
                    _warn("wa_numbers other row", detail)
            if not found:
                good = _fail("expected meta_phone_number_id not linked", EXPECTED_META_PHONE_NUMBER_ID)

        latest = conn.execute(
            text(
                """
                SELECT status, kind, last_error_code, left(coalesce(last_error_detail,''), 240), created_at
                FROM wa_outbox
                ORDER BY created_at DESC
                LIMIT 3
                """
            )
        ).all()
        if latest:
            for row in latest:
                status, kind, code, detail, created_at = row
                if status == "DEAD":
                    _warn("recent DEAD outbox", f"{created_at} {kind} {code} {detail}")
                else:
                    _ok("recent outbox", f"{created_at} {kind} {status}")
        else:
            _warn("wa_outbox", "no rows yet")

        try:
            conn.execute(text("SELECT customer_service_window_expires_at FROM inbox_chats LIMIT 0"))
            _ok("Chat P column", "customer_service_window_expires_at")
        except Exception:
            good = _fail("Chat P migration", "run: alembic upgrade head (0021_phase5_service_window)")

        pol_row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
            {"k": POLICY_KEY},
        ).fetchone()
        policy = merge_service_window_policy(pol_row[0] if pol_row else None)
        fb = policy.get("fallback_templates") or {}
        if not fb:
            _warn(
                "service window templates",
                "fallback_templates empty — expired-window AI/AGENT sends will DEAD until "
                "set_service_window_templates.py",
            )
        else:
            _ok("service window templates", f"keys={list(fb.keys())}")
    return good


def main() -> int:
    print("=== Real WhatsApp Preflight ===")
    checks: list[bool] = []
    checks.append(check_env_token())
    checks.append(check_meta_token())
    checks.append(check_db())
    checks.append(check_http("Ollama :11435", "http://127.0.0.1:11435/api/tags", "llama3.2"))
    checks.append(check_http("ai_engine :8083", "http://127.0.0.1:8083/health", "llm_fallback_configured"))
    checks.append(check_http("wa_gateway :8081", "http://127.0.0.1:8081/health", "gate1-2026-05-15"))
    checks.append(check_http("client_api :8085", "http://127.0.0.1:8085/health"))

    print("")
    if all(checks):
        print("READY: preflight passed. You can reset chat, send inbound, and expect outbox_sender to use Meta.")
        return 0
    print("NOT READY: fix FAIL lines above before real WhatsApp test.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
