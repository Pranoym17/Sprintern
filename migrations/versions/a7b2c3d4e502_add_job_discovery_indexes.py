"""add job discovery indexes

Revision ID: a7b2c3d4e502
Revises: f6a1c2d3e401
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7b2c3d4e502"
down_revision: str | Sequence[str] | None = "f6a1c2d3e401"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_jobs_discovery_fts ON jobs USING gin "
        "(to_tsvector('english', title || ' ' || company || ' ' || coalesce(location, '')))"
    )
    op.execute("CREATE INDEX ix_jobs_title_trgm ON jobs USING gin (normalized_title gin_trgm_ops)")
    op.execute(
        "CREATE INDEX ix_jobs_company_trgm ON jobs USING gin "
        "(normalized_company gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_jobs_location_trgm ON jobs USING gin "
        "(coalesce(normalized_location, '') gin_trgm_ops)"
    )
    op.create_index("ix_jobs_deadline", "jobs", ["deadline_at"])
    op.create_index("ix_jobs_reopened", "jobs", ["reopened_at"])


def downgrade() -> None:
    for index in [
        "ix_jobs_reopened",
        "ix_jobs_deadline",
        "ix_jobs_location_trgm",
        "ix_jobs_company_trgm",
        "ix_jobs_title_trgm",
        "ix_jobs_discovery_fts",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {index}")
