"""Option C phase 2: trial days default, v5.3 conversation caps (trial/starter 35/day).

Revision ID: 0017_option_c_phase2_product
Revises: 0016_alerts_pager_config
"""

from __future__ import annotations

import json

from alembic import op

revision = "0017_option_c_phase2_product"
down_revision = "0016_alerts_pager_config"
branch_labels = None
depends_on = None

_LIMITS = {
    "trial": {"soft_warn": 30, "hard_block": 35},
    "starter": {"soft_warn": 30, "hard_block": 35},
    "growth": {"soft_warn": 50000, "hard_block": 60000},
    "pro": {"soft_warn": 200000, "hard_block": 250000},
    "churned": {"soft_warn": 0, "hard_block": 1},
    "_default": {"soft_warn": 30, "hard_block": 35},
}


def upgrade() -> None:
    limits_json = json.dumps(_LIMITS).replace("'", "''")
    op.execute(
        f"""
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES ('product.trial_days_default', '3'::jsonb)
        ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;
        """
    )
    op.execute(
        f"""
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'usage.daily_inbound_limits',
          '{limits_json}'::jsonb
        )
        ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;
        """
    )
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'm2.usage_hard_customer_reply',
          '"You''ve reached today''s message limit on your plan. Please upgrade or try again tomorrow."'::jsonb
        )
        ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;
        """
    )
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'product.plan_display_aliases',
          '{"growth": "Enterprise", "enterprise": "growth"}'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'product.trial_days_default';")
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'm2.usage_hard_customer_reply';")
    op.execute("DELETE FROM ops_runtime_config WHERE key = 'product.plan_display_aliases';")
    # usage.daily_inbound_limits left as-is on downgrade (shared with 0005)
