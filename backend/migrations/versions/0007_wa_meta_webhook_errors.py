"""Optional Meta webhook error sink (M2 gateway observability)

Revision ID: 0007_wa_meta_webhook_errors
Revises: 0006_ops_sops
Create Date: 2026-05-14

"""

from __future__ import annotations

from alembic import op

revision = "0007_wa_meta_webhook_errors"
down_revision = "0006_ops_sops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_meta_webhook_errors (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          raw_json JSONB NOT NULL
        );
        CREATE INDEX IF NOT EXISTS wa_meta_webhook_errors_received_idx
          ON wa_meta_webhook_errors(received_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wa_meta_webhook_errors;")
