"""Seed India pricing keys in ops_runtime_config (M8 control plane).

Revision ID: 0013_pricing_in_seeds
Revises: 0012_day1_sop_seed
"""

from __future__ import annotations

from alembic import op

revision = "0013_pricing_in_seeds"
down_revision = "0012_day1_sop_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('pricing.in.currency', '"INR"'::jsonb),
          ('pricing.in.upi_minor_units', '49900'::jsonb),
          ('pricing.in.card_minor_units', '59900'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config
        WHERE key IN (
          'pricing.in.currency',
          'pricing.in.upi_minor_units',
          'pricing.in.card_minor_units'
        );
        """
    )
