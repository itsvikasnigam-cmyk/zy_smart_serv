"""Ensure BILLING_WEBHOOK_PROCESSING_ERROR is in alerts.sop_trigger_map.

Revision ID: 0014_sop_trigger_map_billing
Revises: 0013_pricing_in_seeds
"""

from __future__ import annotations

from alembic import op

revision = "0014_sop_trigger_map_billing"
down_revision = "0013_pricing_in_seeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ops_runtime_config
        SET value_json = COALESCE(value_json, '{}'::jsonb)
          || '{"BILLING_WEBHOOK_PROCESSING_ERROR": "payment-failure"}'::jsonb
        WHERE key = 'alerts.sop_trigger_map';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ops_runtime_config
        SET value_json = value_json - 'BILLING_WEBHOOK_PROCESSING_ERROR'
        WHERE key = 'alerts.sop_trigger_map';
        """
    )
