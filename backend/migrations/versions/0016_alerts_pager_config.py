"""Seed alerts.pager runtime config (Slack webhook URL in JSON).

Revision ID: 0016_alerts_pager_config
Revises: 0015_ops_run_logs_alert_trigger
"""

from __future__ import annotations

from alembic import op

revision = "0016_alerts_pager_config"
down_revision = "0015_ops_run_logs_alert_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES ('alerts.pager', '{"slack_webhook_url": ""}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'alerts.pager';")
