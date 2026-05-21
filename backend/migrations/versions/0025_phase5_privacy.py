"""Chat V: customer blocklist/DND + privacy.policy seed.

Revision ID: 0025_phase5_privacy
Revises: 0024_client_catalog
"""

from __future__ import annotations

import json

from alembic import op

revision = "0025_phase5_privacy"
down_revision = "0024_client_catalog"
branch_labels = None
depends_on = None

_DEFAULT_POLICY = {
    "blocklist_mode": "handoff",
    "blocklist_customer_reply": (
        "Thanks for your message. We are unable to process automated replies for this number. "
        "A team member will follow up if needed."
    ),
    "telemetry_retention_days": 30,
    "redaction_enabled": True,
}


def upgrade() -> None:
    policy_json = json.dumps(_DEFAULT_POLICY).replace("'", "''")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS customer_blocks (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          customer_phone_e164 TEXT NOT NULL,
          block_type TEXT NOT NULL DEFAULT 'blocklist',
          reason TEXT,
          source TEXT NOT NULL DEFAULT 'manual',
          active BOOLEAN NOT NULL DEFAULT true,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (client_id, customer_phone_e164)
        );
        CREATE INDEX IF NOT EXISTS customer_blocks_client_phone_idx
          ON customer_blocks(client_id, customer_phone_e164) WHERE active = true;

        INSERT INTO ops_runtime_config (key, value_json)
        VALUES ('privacy.policy', '{policy_json}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config WHERE key = 'privacy.policy';
        DROP TABLE IF EXISTS customer_blocks;
        """
    )
