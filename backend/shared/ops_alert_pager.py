"""M7 phase-2: optional Slack webhook when a new ops alert is inserted."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.shared.config import settings

log = logging.getLogger("ops_alert_pager")

PAGER_CONFIG_KEY = "alerts.pager"


def _slack_url_from_config(conn: Connection) -> str:
    env_url = (settings.ops_alert_slack_webhook_url or "").strip()
    if env_url:
        return env_url
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": PAGER_CONFIG_KEY},
    ).fetchone()
    if not row or not isinstance(row[0], dict):
        return ""
    raw = row[0].get("slack_webhook_url")
    return str(raw).strip() if raw else ""


def maybe_page_slack_for_alert(
    conn: Connection,
    *,
    alert_type: str,
    severity: str,
    summary: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Best-effort Slack incoming webhook; never raises."""
    url = _slack_url_from_config(conn)
    if not url or not url.startswith("https://"):
        return
    text_body = (
        f"[{severity}] {alert_type}\n"
        f"{summary[:1500]}\n"
        f"detail: {json.dumps(detail or {}, separators=(',', ':'))[:500]}"
    )
    payload = json.dumps({"text": text_body}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status >= 300:
                log.warning("slack pager HTTP %s", resp.status)
    except urllib.error.URLError as e:
        log.warning("slack pager failed: %s", e)
    except Exception:
        log.exception("slack pager unexpected error")
