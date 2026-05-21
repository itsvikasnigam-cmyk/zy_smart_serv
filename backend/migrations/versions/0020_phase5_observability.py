"""Option C phase 5: telemetry_trace_logs + misfires_log.

Revision ID: 0020_phase5_observability
Revises: 0019_option_c_phase4_owner_sla
"""

from __future__ import annotations

from alembic import op

revision = "0020_phase5_observability"
down_revision = "0019_option_c_phase4_owner_sla"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_trace_logs (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          trace_id TEXT NOT NULL,
          client_id UUID REFERENCES api_clients(id) ON DELETE SET NULL,
          chat_id UUID REFERENCES inbox_chats(id) ON DELETE SET NULL,
          service TEXT NOT NULL,
          route TEXT NOT NULL,
          latency_ms INT NOT NULL DEFAULT 0,
          cost_inr NUMERIC(12, 4),
          status TEXT NOT NULL DEFAULT 'ok',
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS telemetry_trace_logs_created_idx
          ON telemetry_trace_logs(created_at DESC);
        CREATE INDEX IF NOT EXISTS telemetry_trace_logs_trace_idx
          ON telemetry_trace_logs(trace_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS misfires_log (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          trace_id TEXT,
          client_id UUID REFERENCES api_clients(id) ON DELETE SET NULL,
          chat_id UUID REFERENCES inbox_chats(id) ON DELETE SET NULL,
          source TEXT NOT NULL,
          reason TEXT NOT NULL,
          batch_text_preview TEXT,
          detail JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS misfires_log_created_idx
          ON misfires_log(created_at DESC);
        CREATE INDEX IF NOT EXISTS misfires_log_source_idx
          ON misfires_log(source, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS misfires_log;")
    op.execute("DROP TABLE IF EXISTS telemetry_trace_logs;")
