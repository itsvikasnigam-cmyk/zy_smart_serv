"""Allow trigger_type='alert' on ops_run_logs (M9 auto-trigger).

Revision ID: 0015_ops_run_logs_alert_trigger
Revises: 0014_sop_trigger_map_billing
"""

from __future__ import annotations

from alembic import op

revision = "0015_ops_run_logs_alert_trigger"
down_revision = "0014_sop_trigger_map_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;
        ALTER TABLE ops_run_logs ADD CONSTRAINT ops_run_logs_trigger_type_check
          CHECK (trigger_type IN ('manual', 'auto', 'alert'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;
        ALTER TABLE ops_run_logs ADD CONSTRAINT ops_run_logs_trigger_type_check
          CHECK (trigger_type IN ('manual', 'auto'));
        """
    )
