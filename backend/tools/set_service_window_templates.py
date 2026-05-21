"""Set wa.service_window.policy fallback_templates in ops_runtime_config.

Usage (repo root):
  python backend/tools/set_service_window_templates.py --template hello_world --language en_US
  python backend/tools/set_service_window_templates.py --kind AI_REPLY --template my_tpl --language en
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.db import engine
from backend.shared.wa_service_window import POLICY_KEY, merge_service_window_policy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Approved Meta template name")
    ap.add_argument("--language", default="en_US")
    ap.add_argument("--kind", default="default", help="Outbox kind key or default")
    args = ap.parse_args()

    kind = (args.kind or "default").strip().upper()
    spec = {"template_name": args.template.strip(), "language": args.language.strip()}

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
            {"k": POLICY_KEY},
        ).fetchone()
        policy = merge_service_window_policy(row[0] if row else None)
        fb = dict(policy.get("fallback_templates") or {})
        fb[kind if kind != "DEFAULT" else "default"] = spec
        policy["fallback_templates"] = fb
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:k, CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"k": POLICY_KEY, "v": json.dumps(policy)},
        )

    print(f"OK {POLICY_KEY} fallback_templates[{kind!r}] = {spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
