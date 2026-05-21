"""Print Option C phase 4 owner-wait + SLA config."""

from __future__ import annotations

from backend.shared.db import engine
from backend.shared.inbox_sla_config import load_agent_sla_config, load_owner_wait_config


def main() -> int:
    with engine.connect() as conn:
        ow = load_owner_wait_config(conn)
        sla = load_agent_sla_config(conn)
    print("=== Phase 4 (owner-wait + SLA) ===")
    print(f"owner_wait.realert_hours: {ow.realert_hours}")
    print(f"owner_wait.apology_hours: {ow.apology_hours}")
    print(f"agent_sla.response_minutes: {sla.response_minutes}")
    print(f"apology_reply (first 80 chars): {ow.apology_customer_reply[:80]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
