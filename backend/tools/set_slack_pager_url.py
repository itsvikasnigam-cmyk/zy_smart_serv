"""Set Slack webhook URL in ops_runtime_config alerts.pager (for M7 paging).

Usage:

    python backend/tools/set_slack_pager_url.py https://hooks.slack.com/services/XXX/YYY/ZZZ
"""

from __future__ import annotations

import json
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python backend/tools/set_slack_pager_url.py <slack_webhook_url>")
        return 1
    url = sys.argv[1].strip()
    payload = json.dumps({"slack_webhook_url": url})
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES ('alerts.pager', CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"v": payload},
        )
    print("OK: alerts.pager slack_webhook_url updated.")
    print("Fire a test alert: python backend\\tools\\fire_test_alert.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
