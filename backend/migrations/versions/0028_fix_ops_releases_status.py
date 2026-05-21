"""Fix ops_releases.status CHECK to allow promoted (Chat Z repair).

Some dev DBs created ops_releases before 0011 used a narrower status enum.
Revision ID: 0028_fix_ops_releases_status
Revises: 0027_release_canary
"""

from __future__ import annotations

from alembic import op

revision = "0028_fix_ops_releases_status"
down_revision = "0027_release_canary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ops_releases DROP CONSTRAINT IF EXISTS ops_releases_status_check;
        UPDATE ops_releases SET status = 'promoted' WHERE status IN ('active', 'production', 'live');
        UPDATE ops_releases SET status = 'candidate' WHERE status NOT IN ('candidate', 'promoted', 'rolled_back');
        ALTER TABLE ops_releases
          ADD CONSTRAINT ops_releases_status_check
          CHECK (status IN ('candidate', 'promoted', 'rolled_back'));
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE ops_releases DROP CONSTRAINT IF EXISTS ops_releases_status_check;")
