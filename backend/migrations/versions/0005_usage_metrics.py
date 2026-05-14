"""Chat K: bill_usage_daily + metrics rollups + worker cursors

Revision ID: 0005_usage_metrics
Revises: 0004_billing
Create Date: 2026-05-13

"""

from __future__ import annotations

from alembic import op

revision = "0005_usage_metrics"
down_revision = "0004_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_usage_cursors (
          worker_key TEXT PRIMARY KEY,
          cursor_timestamp TIMESTAMPTZ NOT NULL,
          cursor_message_id UUID NOT NULL
        );
        INSERT INTO worker_usage_cursors (worker_key, cursor_timestamp, cursor_message_id)
        VALUES (
          'inbox_messages_usage',
          TIMESTAMPTZ '1970-01-01T00:00:00Z',
          '00000000-0000-0000-0000-000000000000'::uuid
        )
        ON CONFLICT (worker_key) DO NOTHING;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_usage_daily (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          usage_date DATE NOT NULL,
          inbound_customer_messages BIGINT NOT NULL DEFAULT 0,
          outbound_ai_messages BIGINT NOT NULL DEFAULT 0,
          outbound_agent_messages BIGINT NOT NULL DEFAULT 0,
          outbound_system_messages BIGINT NOT NULL DEFAULT 0,
          soft_threshold_crossed_at TIMESTAMPTZ,
          hard_threshold_crossed_at TIMESTAMPTZ,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (client_id, usage_date)
        );
        CREATE INDEX IF NOT EXISTS bill_usage_daily_date_idx ON bill_usage_daily(usage_date);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_daily_client (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          metric_date DATE NOT NULL,
          customer_messages INT NOT NULL DEFAULT 0,
          ai_messages INT NOT NULL DEFAULT 0,
          agent_messages INT NOT NULL DEFAULT 0,
          system_messages INT NOT NULL DEFAULT 0,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (client_id, metric_date)
        );
        CREATE INDEX IF NOT EXISTS metrics_daily_client_date_idx ON metrics_daily_client(metric_date);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_daily_agent (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          agent_user_id UUID NOT NULL REFERENCES api_users(id) ON DELETE CASCADE,
          metric_date DATE NOT NULL,
          replies_count INT NOT NULL DEFAULT 0,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (client_id, agent_user_id, metric_date)
        );
        CREATE INDEX IF NOT EXISTS metrics_daily_agent_date_idx ON metrics_daily_agent(metric_date);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_hourly_system (
          hour_bucket_utc TIMESTAMPTZ NOT NULL,
          customer_in_messages INT NOT NULL DEFAULT 0,
          ai_out_messages INT NOT NULL DEFAULT 0,
          agent_out_messages INT NOT NULL DEFAULT 0,
          wa_outbox_rows_created INT NOT NULL DEFAULT 0,
          wa_outbox_rows_dead INT NOT NULL DEFAULT 0,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (hour_bucket_utc)
        );
        """
    )

    # Default inbound caps per entitlement (UTC calendar day). Chat B (M2) reads
    # bill_usage_daily + this key; adjust in ops_runtime_config without deploy.
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'usage.daily_inbound_limits',
          '{
            "trial": {"soft_warn": 800, "hard_block": 1000},
            "starter": {"soft_warn": 8000, "hard_block": 10000},
            "growth": {"soft_warn": 50000, "hard_block": 60000},
            "pro": {"soft_warn": 200000, "hard_block": 250000},
            "churned": {"soft_warn": 0, "hard_block": 1}
          }'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'usage.daily_inbound_limits';")
    op.execute("DROP TABLE IF EXISTS metrics_hourly_system;")
    op.execute("DROP TABLE IF EXISTS metrics_daily_agent;")
    op.execute("DROP TABLE IF EXISTS metrics_daily_client;")
    op.execute("DROP TABLE IF EXISTS bill_usage_daily;")
    op.execute("DROP TABLE IF EXISTS worker_usage_cursors;")
