"""Blueprint remainder: ops releases, LLM daily usage, trigger_type CHECK, alert SOP map seed.

Revision ID: 0011_blueprint_remainder
Revises: 0010_m6_m7_broadcast_alerts
"""

from __future__ import annotations

from alembic import op

revision = "0011_blueprint_remainder"
down_revision = "0010_m6_m7_broadcast_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_releases (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          build_id TEXT NOT NULL,
          git_sha TEXT,
          status TEXT NOT NULL DEFAULT 'candidate'
            CHECK (status IN ('candidate', 'promoted', 'rolled_back')),
          registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          promoted_at TIMESTAMPTZ,
          notes TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ops_releases_build_id_uniq
          ON ops_releases(build_id);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_llm_daily_usage (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          usage_date DATE NOT NULL,
          call_count INT NOT NULL DEFAULT 0,
          PRIMARY KEY (client_id, usage_date)
        );
        """
    )
    op.execute(
        """
        ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;
        ALTER TABLE ops_run_logs ADD CONSTRAINT ops_run_logs_trigger_type_check
          CHECK (trigger_type IN ('manual', 'auto', 'alert'));
        """
    )
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'alerts.sop_trigger_map',
          '{"OUTBOX_DEAD_SPIKE": "dead-letter-recovery", '
          '"META_WEBHOOK_ERROR_SPIKE": "webhook-downtime", '
          '"BILLING_WEBHOOK_PROCESSING_ERROR": "payment-failure"}'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'alerts.sop_trigger_map';")
    op.execute(
        "ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;"
    )
    op.execute("DROP TABLE IF EXISTS ai_llm_daily_usage;")
    op.execute("DROP TABLE IF EXISTS ops_releases;")
