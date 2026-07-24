"""add durable background jobs

Revision ID: i5d0e1f2a340
Revises: h4c9d0e1f239
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i5d0e1f2a340"
down_revision: str | None = "h4c9d0e1f239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = (
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
    "jobs",
    "job_sources",
    "job_change_events",
    "anonymous_outcome_aggregates",
    "email_suppressions",
    "email_provider_events",
    "source_states",
    "ingestion_runs",
    "scheduler_runtimes",
    "source_configurations",
    "source_audit_logs",
    "parser_alerts",
)


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency"),
    )
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_available_at", "background_jobs", ["available_at"])
    op.create_index("ix_background_jobs_correlation_id", "background_jobs", ["correlation_id"])
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON background_jobs TO sprintern_worker"
    )
    op.execute("GRANT SELECT ON alembic_version TO sprintern_worker")
    for table in RLS_TABLES:
        op.execute(
            f'CREATE POLICY "{table}_worker_access" ON "{table}" '
            "FOR ALL TO sprintern_worker USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_worker_access" ON "{table}"')
    op.execute("REVOKE SELECT ON alembic_version FROM sprintern_worker")
    op.drop_index("ix_background_jobs_correlation_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_available_at", table_name="background_jobs")
    op.drop_index("ix_background_jobs_job_type", table_name="background_jobs")
    op.drop_table("background_jobs")
