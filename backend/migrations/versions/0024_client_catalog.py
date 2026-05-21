"""Chat U: tenant catalog items for deterministic price/stock answers.

Revision ID: 0024_client_catalog
Revises: 0023_phase5_cost_margin
"""

from __future__ import annotations

from alembic import op

revision = "0024_client_catalog"
down_revision = "0023_phase5_cost_margin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS client_catalog_items (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          sku TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT,
          price_inr NUMERIC(12, 2),
          stock_qty INT NOT NULL DEFAULT 0,
          active BOOLEAN NOT NULL DEFAULT true,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (client_id, sku)
        );
        CREATE INDEX IF NOT EXISTS client_catalog_items_client_idx
          ON client_catalog_items(client_id) WHERE active = true;
        CREATE INDEX IF NOT EXISTS client_catalog_items_name_idx
          ON client_catalog_items(client_id, lower(name));
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS client_catalog_items;")
