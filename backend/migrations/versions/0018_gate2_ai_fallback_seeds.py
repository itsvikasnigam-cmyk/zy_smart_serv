"""Option C phase 3: seed ai.fallback.* ops_runtime_config keys (disabled by default).

Revision ID: 0018_gate2_ai_fallback_seeds
Revises: 0017_option_c_phase2_product
"""

from __future__ import annotations

from alembic import op

revision = "0018_gate2_ai_fallback_seeds"
down_revision = "0017_option_c_phase2_product"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json) VALUES
          ('ai.fallback.enabled', 'false'::jsonb),
          ('ai.fallback.use_judge', 'false'::jsonb),
          ('ai.fallback.quality_threshold', '0.65'::jsonb),
          ('ai.fallback.max_primary_tokens', '512'::jsonb),
          ('ai.fallback.max_judge_tokens', '256'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config
        WHERE key IN (
          'ai.fallback.enabled',
          'ai.fallback.use_judge',
          'ai.fallback.quality_threshold',
          'ai.fallback.max_primary_tokens',
          'ai.fallback.max_judge_tokens'
        );
        """
    )
