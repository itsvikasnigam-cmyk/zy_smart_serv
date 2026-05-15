"""M5 billing: India KYC storage + bill_invoices

Revision ID: 0009_billing_kyc_invoices
Revises: 0008_inbox_blueprint_states
Create Date: 2026-05-14

"""

from __future__ import annotations

from alembic import op

revision = "0009_billing_kyc_invoices"
down_revision = "0008_inbox_blueprint_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE api_clients
          ADD COLUMN IF NOT EXISTS kyc_india_json JSONB,
          ADD COLUMN IF NOT EXISTS kyc_submitted_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS kyc_verified_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_invoices (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          provider TEXT NOT NULL CHECK (provider IN ('razorpay','paddle')),
          external_invoice_id TEXT NOT NULL,
          amount_minor BIGINT,
          currency TEXT,
          status TEXT NOT NULL DEFAULT 'unknown',
          issued_at TIMESTAMPTZ,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(provider, external_invoice_id)
        );
        CREATE INDEX IF NOT EXISTS bill_invoices_client_idx ON bill_invoices(client_id, issued_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bill_invoices;")
    op.execute(
        """
        ALTER TABLE api_clients
          DROP COLUMN IF EXISTS kyc_india_json,
          DROP COLUMN IF EXISTS kyc_submitted_at,
          DROP COLUMN IF EXISTS kyc_verified_at;
        """
    )
