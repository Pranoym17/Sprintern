# ruff: noqa: E501
"""add product data foundation

Revision ID: f6a1c2d3e401
Revises: e4f3b2a19001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1c2d3e401"
down_revision: str | Sequence[str] | None = "e4f3b2a19001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "filters", sa.Column("remote_only", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("filters", sa.Column("radius_km", sa.Integer(), nullable=True))
    op.add_column("filters", sa.Column("center_latitude", sa.Float(), nullable=True))
    op.add_column("filters", sa.Column("center_longitude", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_filters_radius", "filters", "radius_km IS NULL OR radius_km BETWEEN 1 AND 500"
    )
    op.add_column("jobs", sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("deadline_source", sa.String(16), nullable=True))
    op.add_column(
        "jobs", sa.Column("title_incomplete", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("jobs", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_jobs_deadline_source",
        "jobs",
        "deadline_source IS NULL OR deadline_source IN ('source','inferred','user')",
    )

    op.execute("""
    CREATE TABLE job_interactions (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
      bookmarked_at timestamptz, hidden_at timestamptz, not_interested_reason varchar(64),
      first_viewed_at timestamptz, last_viewed_at timestamptz, view_count integer NOT NULL DEFAULT 0,
      deadline_override_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_job_interactions_profile_job UNIQUE(profile_id, job_id)
    );
    CREATE INDEX ix_job_interactions_profile_recent ON job_interactions(profile_id, last_viewed_at);
    CREATE INDEX ix_job_interactions_profile_hidden ON job_interactions(profile_id, hidden_at);

    CREATE TABLE applications (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
      stage varchar(16) NOT NULL DEFAULT 'saved' CHECK(stage IN ('saved','preparing','applied','oa','interview','offer','rejected','withdrawn')),
      notes text, deadline_at timestamptz, follow_up_at timestamptz, interview_at timestamptz,
      contact varchar(300), resume_version varchar(200), application_url text, applied_at timestamptz,
      outcome varchar(100), import_key varchar(64), created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_applications_profile_job UNIQUE(profile_id, job_id)
    );
    CREATE INDEX ix_applications_profile_stage ON applications(profile_id, stage);
    CREATE INDEX ix_applications_profile_follow_up ON applications(profile_id, follow_up_at);

    CREATE TABLE application_events (
      id uuid PRIMARY KEY, application_id uuid NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
      profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE, event_type varchar(40) NOT NULL,
      data jsonb NOT NULL DEFAULT '{}'::jsonb, corrected_event_id uuid REFERENCES application_events(id) ON DELETE SET NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_application_events_application_created ON application_events(application_id, created_at);

    CREATE TABLE job_change_events (
      id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
      event_type varchar(32) NOT NULL, changes jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_job_change_events_job_created ON job_change_events(job_id, created_at);

    CREATE TABLE job_reports (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
      reason varchar(16) NOT NULL CHECK(reason IN ('closed','duplicate','suspicious','inaccurate')),
      details varchar(500), resolved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(profile_id, job_id, reason)
    );
    CREATE INDEX ix_job_reports_job_status ON job_reports(job_id, resolved_at);

    CREATE TABLE share_links (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, token_hash varchar(64) NOT NULL UNIQUE,
      expires_at timestamptz NOT NULL, revoked_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_share_links_profile ON share_links(profile_id);

    CREATE TABLE company_watchlists (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      company varchar(200) NOT NULL, normalized_company varchar(200) NOT NULL,
      terms jsonb NOT NULL DEFAULT '[]'::jsonb, locations jsonb NOT NULL DEFAULT '[]'::jsonb,
      active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(profile_id, normalized_company)
    );
    CREATE INDEX ix_watchlists_profile_active ON company_watchlists(profile_id, active);

    CREATE TABLE filter_exclusions (
      id uuid PRIMARY KEY, filter_id uuid NOT NULL REFERENCES filters(id) ON DELETE CASCADE,
      kind varchar(16) NOT NULL CHECK(kind IN ('keyword','company','location')),
      value varchar(200) NOT NULL, normalized_value varchar(200) NOT NULL,
      UNIQUE(filter_id, kind, normalized_value)
    );
    CREATE INDEX ix_filter_exclusions_filter ON filter_exclusions(filter_id);

    CREATE TABLE filter_notification_overrides (
      filter_id uuid PRIMARY KEY REFERENCES filters(id) ON DELETE CASCADE,
      profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      email_enabled boolean, telegram_enabled boolean,
      cadence varchar(16) CHECK(cadence IS NULL OR cadence IN ('instant','hourly','daily','weekly')),
      priority varchar(16) NOT NULL DEFAULT 'normal' CHECK(priority IN ('normal','high')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_filter_notification_overrides_profile_id ON filter_notification_overrides(profile_id);

    CREATE TABLE reminder_events (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
      application_id uuid REFERENCES applications(id) ON DELETE CASCADE,
      kind varchar(16) NOT NULL CHECK(kind IN ('deadline','follow_up','interview','saved','preparing')),
      due_at timestamptz NOT NULL, idempotency_key varchar(255) NOT NULL UNIQUE, sent_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_reminders_profile_due ON reminder_events(profile_id, due_at, sent_at);

    CREATE TABLE weekly_goals (
      id uuid PRIMARY KEY, profile_id uuid NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
      target integer NOT NULL DEFAULT 5 CHECK(target BETWEEN 0 AND 100),
      reminders_enabled boolean NOT NULL DEFAULT false, streaks_enabled boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE source_configurations (
      id uuid PRIMARY KEY, source varchar(32) NOT NULL, source_key varchar(255) NOT NULL,
      configuration jsonb NOT NULL DEFAULT '{}'::jsonb, enabled boolean NOT NULL DEFAULT false,
      last_validated_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source, source_key)
    );
    CREATE INDEX ix_source_config_enabled ON source_configurations(enabled);

    CREATE TABLE parser_alerts (
      id uuid PRIMARY KEY, source_key varchar(255) NOT NULL, fingerprint varchar(64) NOT NULL,
      message varchar(500) NOT NULL, occurrences integer NOT NULL DEFAULT 1, resolved_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(source_key, fingerprint)
    );
    CREATE INDEX ix_parser_alert_unresolved ON parser_alerts(resolved_at);

    CREATE TABLE anonymous_outcome_aggregates (
      id uuid PRIMARY KEY, week_start date NOT NULL, normalized_role varchar(100) NOT NULL,
      stage varchar(16) NOT NULL, count integer NOT NULL DEFAULT 0, conversion_rate double precision,
      UNIQUE(week_start, normalized_role, stage)
    );
    """)

    protected = [
        "profiles",
        "filters",
        "matches",
        "notification_deliveries",
        "telegram_link_tokens",
        "jobs",
        "job_sources",
        "job_interactions",
        "applications",
        "application_events",
        "job_change_events",
        "job_reports",
        "share_links",
        "company_watchlists",
        "filter_exclusions",
        "filter_notification_overrides",
        "reminder_events",
        "weekly_goals",
        "source_configurations",
        "parser_alerts",
        "anonymous_outcome_aggregates",
        "source_states",
        "ingestion_runs",
        "scheduler_runtimes",
        "email_suppressions",
        "email_provider_events",
    ]
    for table in protected:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
              EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM anon';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
              EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM authenticated';
            END IF;
            END $$"""
        )


def downgrade() -> None:
    for table in [
        "anonymous_outcome_aggregates",
        "parser_alerts",
        "source_configurations",
        "weekly_goals",
        "reminder_events",
        "filter_notification_overrides",
        "filter_exclusions",
        "company_watchlists",
        "share_links",
        "job_reports",
        "job_change_events",
        "application_events",
        "applications",
        "job_interactions",
    ]:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    op.drop_constraint("ck_jobs_deadline_source", "jobs", type_="check")
    for column in [
        "longitude",
        "latitude",
        "title_incomplete",
        "deadline_source",
        "deadline_at",
        "reopened_at",
    ]:
        op.drop_column("jobs", column)
    op.drop_constraint("ck_filters_radius", "filters", type_="check")
    for column in ["center_longitude", "center_latitude", "radius_km", "remote_only"]:
        op.drop_column("filters", column)
