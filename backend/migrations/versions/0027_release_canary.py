"""Chat Z: release registry audit columns, events, canary policy seed.

Revision ID: 0027_release_canary
Revises: 0026_ops_tasks
"""

from __future__ import annotations

import json

from alembic import op

revision = "0027_release_canary"
down_revision = "0026_ops_tasks"
branch_labels = None
depends_on = None

_CANARY = {
    "enabled": False,
    "percent": 0,
    "active_build_id": None,
    "canary_primary_model": None,
}
_CHECKLIST = {
    "items": [
        "Run pytest and integration smoke on candidate build",
        "Review ai_engine / wa_gateway / billing_api diff for breaking API contracts",
        "Confirm ops_runtime_config prompt/routing changes documented",
        "Super_admin sign-off recorded in ops_release_events",
        "Canary percent starts at 0; enable only after promote",
    ]
}

_CANARY_JSON = json.dumps(_CANARY).replace("'", "''")
_CHECKLIST_JSON = json.dumps(_CHECKLIST).replace("'", "''")


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE ops_releases
          ADD COLUMN IF NOT EXISTS artifact_hash TEXT,
          ADD COLUMN IF NOT EXISTS test_report_hash TEXT,
          ADD COLUMN IF NOT EXISTS registered_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS promoted_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS rolled_back_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL;

        CREATE TABLE IF NOT EXISTS ops_release_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          release_id UUID NOT NULL REFERENCES ops_releases(id) ON DELETE CASCADE,
          action TEXT NOT NULL CHECK (action IN ('registered', 'promoted', 'rolled_back', 'canary_disabled')),
          actor_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ops_release_events_release_idx
          ON ops_release_events(release_id, created_at DESC);

        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('release.canary_policy', '{_CANARY_JSON}'::jsonb),
          ('release.approval_checklist', '{_CHECKLIST_JSON}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config
        WHERE key IN ('release.canary_policy', 'release.approval_checklist');
        DROP TABLE IF EXISTS ops_release_events;
        ALTER TABLE ops_releases
          DROP COLUMN IF EXISTS rolled_back_by_user_id,
          DROP COLUMN IF EXISTS rolled_back_at,
          DROP COLUMN IF EXISTS promoted_by_user_id,
          DROP COLUMN IF EXISTS registered_by_user_id,
          DROP COLUMN IF EXISTS test_report_hash,
          DROP COLUMN IF EXISTS artifact_hash;
        """
    )
