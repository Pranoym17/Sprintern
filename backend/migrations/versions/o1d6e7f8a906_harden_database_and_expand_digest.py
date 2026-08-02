"""harden database advisor findings and expand digest size

Revision ID: o1d6e7f8a906
Revises: n0c5d6e7f895
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "o1d6e7f8a906"
down_revision: str | None = "n0c5d6e7f895"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_profiles_email_digest_job_limit", "profiles", type_="check")
    op.create_check_constraint(
        "ck_profiles_email_digest_job_limit",
        "profiles",
        "email_digest_job_limit BETWEEN 1 AND 15",
    )
    op.alter_column("profiles", "email_digest_job_limit", server_default="15")
    # Move accounts still using the former system default to the new default;
    # explicitly chosen values remain untouched.
    op.execute("UPDATE profiles SET email_digest_job_limit = 15 WHERE email_digest_job_limit = 7")
    op.execute("ALTER FUNCTION public.sprintern_auth_user_id() SET search_path = ''")
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("ALTER EXTENSION pg_trgm SET SCHEMA extensions")
    op.execute("GRANT USAGE ON SCHEMA extensions TO sprintern_api, sprintern_worker")
    op.execute("ALTER TABLE background_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY alembic_version_worker_read ON alembic_version "
        "FOR SELECT TO sprintern_worker USING (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS alembic_version_worker_read ON alembic_version")
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE background_jobs DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE USAGE ON SCHEMA extensions FROM sprintern_api, sprintern_worker")
    op.execute("ALTER EXTENSION pg_trgm SET SCHEMA public")
    op.execute("DROP SCHEMA IF EXISTS extensions")
    op.execute("ALTER FUNCTION public.sprintern_auth_user_id() RESET search_path")
    op.alter_column("profiles", "email_digest_job_limit", server_default="7")
    op.drop_constraint("ck_profiles_email_digest_job_limit", "profiles", type_="check")
    op.create_check_constraint(
        "ck_profiles_email_digest_job_limit",
        "profiles",
        "email_digest_job_limit BETWEEN 1 AND 10",
    )
