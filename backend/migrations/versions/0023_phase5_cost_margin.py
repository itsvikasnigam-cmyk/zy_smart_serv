"""Chat S: daily cost and margin estimates.

Revision ID: 0023_phase5_cost_margin
Revises: 0022_phase5_typing_lock
"""

from __future__ import annotations

from alembic import op

revision = "0023_phase5_cost_margin"
down_revision = "0022_phase5_typing_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE metrics_daily_client
          ADD COLUMN IF NOT EXISTS ai_invocations INT NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS estimated_ai_cost_inr NUMERIC(12, 4) NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS estimated_revenue_inr NUMERIC(12, 4) NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS estimated_margin_inr NUMERIC(12, 4) NOT NULL DEFAULT 0;

        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'metrics.cost_model',
          '{
            "currency": "INR",
            "mode": "local",
            "avg_tokens_per_ai_reply": 350,
            "local_ai_cost_per_1k_tokens_inr": 0.02,
            "cloud_ai_cost_per_1k_tokens_inr": 0.15,
            "monthly_revenue_inr_by_plan": {
              "trial": 0,
              "starter": 999,
              "growth": 2999,
              "pro": 9999,
              "churned": 0
            },
            "daily_cost_alert_threshold_inr": 100
          }'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE metrics_daily_client
          DROP COLUMN IF EXISTS estimated_margin_inr,
          DROP COLUMN IF EXISTS estimated_revenue_inr,
          DROP COLUMN IF EXISTS estimated_ai_cost_inr,
          DROP COLUMN IF EXISTS ai_invocations;
        DELETE FROM ops_runtime_config WHERE key = 'metrics.cost_model';
        """
    )
