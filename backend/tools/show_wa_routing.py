"""Print wa_numbers rows for Gate 1 dev_send_inbound (copy meta_phone_number_id).

Usage:

    cd ...\\empty-window; . .\\dev-env.ps1
    python backend/tools/show_wa_routing.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT phone_e164, meta_phone_number_id, client_id::text, id::text, status
                FROM wa_numbers
                ORDER BY created_at ASC
                """
            )
        ).all()
    if not rows:
        print("No wa_numbers rows. Run:")
        print("  python backend\\tools\\dev_seed.py --meta-phone-number-id 123456789012345 --trial-days 14")
        return 1
    print("=== WhatsApp routing (use meta_phone_number_id in dev_send_inbound) ===\n")
    for r in rows:
        print(f"  phone_e164:          {r[0]}")
        print(f"  meta_phone_number_id: {r[1]}")
        print(f"  client_id:           {r[2]}")
        print(f"  wa_number_id:        {r[3]}")
        print(f"  status:              {r[4]}")
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
