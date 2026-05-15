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
          artifact_hash TEXT,
          test_report_hash TEXT,
          status TEXT NOT NULL DEFAULT 'candidate'
            CHECK (status IN ('candidate', 'current', 'rolled_back', 'archived')),
          notes TEXT,
          promoted_at TIMESTAMPTZ,
          promoted_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          created_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ops_releases_build_id_uniq ON ops_releases(build_id);
        CREATE INDEX IF NOT EXISTS ops_releases_status_created_idx
          ON ops_releases(status, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_llm_daily_usage (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          usage_date DATE NOT NULL,
          call_count INT NOT NULL DEFAULT 0 CHECK (call_count >= 0),
          PRIMARY KEY (client_id, usage_date)
        );
        """
    )
    op.execute(
        """
        UPDATE ops_run_logs
        SET trigger_type = 'manual'
        WHERE trigger_type IS NULL OR TRIM(trigger_type) = '';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ops_run_logs_trigger_type_check'
          ) THEN
            ALTER TABLE ops_run_logs
              ADD CONSTRAINT ops_run_logs_trigger_type_check
              CHECK (trigger_type IN (
                'manual', 'auto', 'scheduled', 'other',
                'alert:outbox_dead_spike', 'alert:meta_webhook_error_spike'
              ));
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('inbox.typing_hard_lock_enabled', 'false'::jsonb),
          ('ai.fallback.max_calls_per_client_per_day', '200'::jsonb),
          ('alerts.sop_trigger_map', '{"OUTBOX_DEAD_SPIKE": "dead-letter-recovery", "META_WEBHOOK_ERROR_SPIKE": "webhook-downtime"}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;")
    op.execute("DROP TABLE IF EXISTS ai_llm_daily_usage;")
    op.execute("DROP TABLE IF EXISTS ops_releases;")
