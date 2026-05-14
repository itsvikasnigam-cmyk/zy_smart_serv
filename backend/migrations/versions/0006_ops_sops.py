"""M9 Chat I: SOP Center — ops_sops, ops_sop_versions, ops_run_logs

Revision ID: 0006_ops_sops
Revises: 0005_usage_metrics
Create Date: 2026-05-13

"""

from __future__ import annotations

from alembic import op

revision = "0006_ops_sops"
down_revision = "0005_usage_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_sops (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          title TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          category TEXT,
          status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'archived')),
          current_version INT NOT NULL DEFAULT 1 CHECK (current_version >= 1),
          created_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          updated_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ops_sops_category_idx ON ops_sops(category);
        CREATE INDEX IF NOT EXISTS ops_sops_status_idx ON ops_sops(status);
        CREATE INDEX IF NOT EXISTS ops_sops_updated_at_idx ON ops_sops(updated_at DESC);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_sop_versions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          sop_id UUID NOT NULL REFERENCES ops_sops(id) ON DELETE CASCADE,
          version_num INT NOT NULL CHECK (version_num >= 1),
          body_markdown TEXT NOT NULL,
          created_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (sop_id, version_num)
        );
        CREATE INDEX IF NOT EXISTS ops_sop_versions_sop_idx ON ops_sop_versions(sop_id, version_num DESC);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_run_logs (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          sop_id UUID NOT NULL REFERENCES ops_sops(id) ON DELETE CASCADE,
          sop_version_at_run INT NOT NULL CHECK (sop_version_at_run >= 1),
          context_json JSONB NOT NULL,
          trigger_type TEXT NOT NULL DEFAULT 'manual',
          created_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          client_id UUID REFERENCES api_clients(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ops_run_logs_sop_created_idx ON ops_run_logs(sop_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS ops_run_logs_client_created_idx ON ops_run_logs(client_id, created_at DESC)
          WHERE client_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ops_run_logs_trigger_created_idx ON ops_run_logs(trigger_type, created_at DESC);
        CREATE INDEX IF NOT EXISTS ops_run_logs_created_idx ON ops_run_logs(created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops_run_logs;")
    op.execute("DROP TABLE IF EXISTS ops_sop_versions;")
    op.execute("DROP TABLE IF EXISTS ops_sops;")
