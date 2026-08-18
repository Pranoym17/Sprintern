"""store API-requested profile rematches on owned profiles

Revision ID: x0a1b2c3d4e5
Revises: w9f4a5b6c784
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "x0a1b2c3d4e5"
down_revision: str | None = "w9f4a5b6c784"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("match_refresh_requested_at", sa.DateTime(timezone=True)))
    op.add_column("profiles", sa.Column("match_refresh_seen_since", sa.DateTime(timezone=True)))
    op.add_column("profiles", sa.Column("match_refresh_locked_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_profiles_pending_match_refresh",
        "profiles",
        ["match_refresh_requested_at"],
        postgresql_where=sa.text("match_refresh_requested_at IS NOT NULL"),
    )
    # The API no longer writes worker-owned rows. Revoking this temporary grant
    # keeps the queue private even if a future route accidentally calls it.
    op.execute("DROP POLICY IF EXISTS background_jobs_api_profile_enqueue ON background_jobs")
    op.execute("REVOKE INSERT ON background_jobs FROM sprintern_api")


def downgrade() -> None:
    op.execute("GRANT INSERT ON background_jobs TO sprintern_api")
    op.execute(
        "CREATE POLICY background_jobs_api_profile_enqueue ON background_jobs "
        "FOR INSERT TO sprintern_api "
        "WITH CHECK ("
        "job_type = 'matching.profile' "
        "AND (payload ->> 'profile_id')::uuid = public.sprintern_auth_user_id()"
        ")"
    )
    op.drop_index("ix_profiles_pending_match_refresh", table_name="profiles")
    op.drop_column("profiles", "match_refresh_locked_at")
    op.drop_column("profiles", "match_refresh_seen_since")
    op.drop_column("profiles", "match_refresh_requested_at")
