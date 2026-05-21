"""Align legacy ops_releases tables with Chat Z expected columns.

Revision ID: 0029_align_ops_releases_schema
Revises: 0028_fix_ops_releases_status
"""

from __future__ import annotations

from alembic import op

revision = "0029_align_ops_releases_schema"
down_revision = "0028_fix_ops_releases_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops_releases
          ADD COLUMN IF NOT EXISTS git_sha TEXT,
          ADD COLUMN IF NOT EXISTS registered_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS notes TEXT,
          ADD COLUMN IF NOT EXISTS artifact_hash TEXT,
          ADD COLUMN IF NOT EXISTS test_report_hash TEXT,
          ADD COLUMN IF NOT EXISTS registered_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS promoted_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS rolled_back_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL;

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'ops_releases' AND column_name = 'created_at'
          ) THEN
            UPDATE ops_releases
            SET registered_at = COALESCE(registered_at, created_at, now())
            WHERE registered_at IS NULL;
          ELSE
            UPDATE ops_releases
            SET registered_at = COALESCE(registered_at, now())
            WHERE registered_at IS NULL;
          END IF;
        END $$;

        ALTER TABLE ops_releases
          ALTER COLUMN registered_at SET DEFAULT now();

        CREATE UNIQUE INDEX IF NOT EXISTS ops_releases_build_id_uniq
          ON ops_releases(build_id);
        """
    )


def downgrade() -> None:
    pass
