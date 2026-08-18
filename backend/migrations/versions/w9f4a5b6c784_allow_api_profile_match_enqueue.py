"""allow API profile-match enqueue

Revision ID: w9f4a5b6c784
Revises: v8e3f4a5b673
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "w9f4a5b6c784"
down_revision: str | None = "v8e3f4a5b673"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The API role may enqueue only a rematch for its authenticated user. It
    # cannot read, claim, mutate, or delete global durable-work records.
    op.execute("GRANT INSERT ON background_jobs TO sprintern_api")
    op.execute(
        "CREATE POLICY background_jobs_api_profile_enqueue ON background_jobs "
        "FOR INSERT TO sprintern_api "
        "WITH CHECK ("
        "job_type = 'matching.profile' "
        "AND (payload ->> 'profile_id')::uuid = public.sprintern_auth_user_id()"
        ")"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS background_jobs_api_profile_enqueue ON background_jobs")
    op.execute("REVOKE INSERT ON background_jobs FROM sprintern_api")
