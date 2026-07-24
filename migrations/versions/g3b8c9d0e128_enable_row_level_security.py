"""enable row level security

Revision ID: g3b8c9d0e128
Revises: f2a7b8c9d017
"""

from collections.abc import Sequence

from alembic import op

revision: str = "g3b8c9d0e128"
down_revision: str | None = "f2a7b8c9d017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_TABLES = {
    "profiles": "id",
    "filters": "profile_id",
    "matches": "profile_id",
    "notification_deliveries": "profile_id",
    "telegram_link_tokens": "profile_id",
    "job_interactions": "profile_id",
    "applications": "profile_id",
    "application_events": "profile_id",
    "job_reports": "profile_id",
    "share_links": "profile_id",
    "company_watchlists": "profile_id",
    "filter_notification_overrides": "profile_id",
    "reminder_events": "profile_id",
    "weekly_goals": "profile_id",
}

READ_ONLY_TABLES = {
    "jobs",
    "job_sources",
    "job_change_events",
    "anonymous_outcome_aggregates",
}

INTERNAL_TABLES = {
    "email_suppressions",
    "email_provider_events",
    "source_states",
    "ingestion_runs",
    "scheduler_runtimes",
    "source_configurations",
    "source_audit_logs",
    "parser_alerts",
}


def upgrade() -> None:
    # PostgREST sets this claim for authenticated requests. The API's database owner
    # continues to enforce ownership in service code and bypasses non-forced RLS.
    op.execute(
        """
        CREATE FUNCTION public.sprintern_auth_user_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT COALESCE(
            NULLIF(current_setting('request.jwt.claim.sub', true), ''),
            NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
          )::uuid
        $$
        """
    )
    for table, owner_column in USER_TABLES.items():
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f"""
            CREATE POLICY "{table}_owner_access" ON "{table}"
            FOR ALL
            USING ("{owner_column}" = public.sprintern_auth_user_id())
            WITH CHECK ("{owner_column}" = public.sprintern_auth_user_id())
            """
        )
    op.execute('ALTER TABLE "filter_exclusions" ENABLE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY "filter_exclusions_owner_access" ON "filter_exclusions"
        FOR ALL
        USING (
          EXISTS (
            SELECT 1 FROM filters
            WHERE filters.id = filter_exclusions.filter_id
              AND filters.profile_id = public.sprintern_auth_user_id()
          )
        )
        WITH CHECK (
          EXISTS (
            SELECT 1 FROM filters
            WHERE filters.id = filter_exclusions.filter_id
              AND filters.profile_id = public.sprintern_auth_user_id()
          )
        )
        """
    )
    for table in READ_ONLY_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f"""
            CREATE POLICY "{table}_authenticated_read" ON "{table}"
            FOR SELECT
            USING (public.sprintern_auth_user_id() IS NOT NULL)
            """
        )
    for table in INTERNAL_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in INTERNAL_TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    for table in READ_ONLY_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_authenticated_read" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "filter_exclusions_owner_access" ON "filter_exclusions"'
    )
    op.execute('ALTER TABLE "filter_exclusions" DISABLE ROW LEVEL SECURITY')
    for table in USER_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_owner_access" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.execute("DROP FUNCTION IF EXISTS public.sprintern_auth_user_id()")
