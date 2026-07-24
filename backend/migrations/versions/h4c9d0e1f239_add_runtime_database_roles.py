"""add runtime database roles

Revision ID: h4c9d0e1f239
Revises: g3b8c9d0e128
"""

from collections.abc import Sequence

from alembic import op

revision: str = "h4c9d0e1f239"
down_revision: str | None = "g3b8c9d0e128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_TABLES = (
    "profiles",
    "filters",
    "matches",
    "notification_deliveries",
    "telegram_link_tokens",
    "job_interactions",
    "applications",
    "application_events",
    "job_reports",
    "share_links",
    "company_watchlists",
    "filter_exclusions",
    "filter_notification_overrides",
    "reminder_events",
    "weekly_goals",
)

USER_READ_TABLES = (
    "jobs",
    "job_sources",
    "job_change_events",
    "anonymous_outcome_aggregates",
    "source_configurations",
    "source_states",
)

ALL_TABLES = (
    *USER_TABLES,
    *USER_READ_TABLES,
    "email_suppressions",
    "email_provider_events",
    "ingestion_runs",
    "scheduler_runtimes",
    "source_audit_logs",
    "parser_alerts",
)


def upgrade() -> None:
    # These are NOLOGIN group roles. Production creates separate login roles with
    # independently managed passwords, then grants exactly one group role to each.
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sprintern_api') THEN
            CREATE ROLE sprintern_api NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sprintern_worker') THEN
            CREATE ROLE sprintern_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
          END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO sprintern_api, sprintern_worker")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(USER_TABLES)} TO sprintern_api")
    op.execute(f"GRANT SELECT ON {', '.join(USER_READ_TABLES)} TO sprintern_api")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(ALL_TABLES)} TO sprintern_worker"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sprintern_worker")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sprintern_api")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sprintern_worker"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO sprintern_worker"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM sprintern_worker"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM sprintern_worker"
    )
    op.execute(f"REVOKE ALL ON {', '.join(ALL_TABLES)} FROM sprintern_worker")
    op.execute(f"REVOKE ALL ON {', '.join((*USER_TABLES, *USER_READ_TABLES))} FROM sprintern_api")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sprintern_api, sprintern_worker")
    op.execute("REVOKE USAGE ON SCHEMA public FROM sprintern_api, sprintern_worker")
    op.execute("DROP ROLE IF EXISTS sprintern_api")
    op.execute("DROP ROLE IF EXISTS sprintern_worker")
