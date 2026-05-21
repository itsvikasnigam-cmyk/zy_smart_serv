"""Chat V: per-tenant customer blocklist / DND registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

BlockType = Literal["blocklist", "dnd"]


@dataclass(frozen=True)
class CustomerBlockHit:
    block_type: BlockType
    reason: str | None


def lookup_customer_block(
    conn: Connection,
    *,
    client_id: str,
    customer_phone_e164: str,
) -> CustomerBlockHit | None:
    row = conn.execute(
        text(
            """
            SELECT block_type, reason
            FROM customer_blocks
            WHERE client_id = CAST(:cid AS uuid)
              AND customer_phone_e164 = :phone
              AND active = true
            LIMIT 1
            """
        ),
        {"cid": client_id, "phone": customer_phone_e164},
    ).fetchone()
    if not row:
        return None
    bt = str(row[0] or "blocklist").strip().lower()
    block_type: BlockType = "dnd" if bt == "dnd" else "blocklist"
    reason = str(row[1]).strip() if row[1] else None
    return CustomerBlockHit(block_type=block_type, reason=reason)
