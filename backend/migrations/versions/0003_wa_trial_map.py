"""wa_trial_map for shared trial WhatsApp number routing

Revision ID: 0003_wa_trial_map
Revises: 0002_reliability_queueing
Create Date: 2026-05-12

"""

from __future__ import annotations

from alembic import op

revision = "0003_wa_trial_map"
down_revision = "0002_reliability_queueing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_trial_map (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          wa_number_id UUID NOT NULL REFERENCES wa_numbers(id) ON DELETE CASCADE,
          customer_phone_e164 TEXT NOT NULL,
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS wa_trial_map_wa_number_customer_uniq
          ON wa_trial_map(wa_number_id, customer_phone_e164);
        CREATE INDEX IF NOT EXISTS wa_trial_map_client_idx ON wa_trial_map(client_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wa_trial_map;")
