"""optimize durable background job claims

Revision ID: v8e3f4a5b673
Revises: u7d2e3f4a562
Create Date: 2026-08-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "v8e3f4a5b673"
down_revision: str | None = "u7d2e3f4a562"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The worker claims only queued rows or expired running leases. Partial
    # indexes prevent completed job history from being scanned and locked.
    op.execute(
        "CREATE INDEX ix_background_jobs_queued_claim "
        "ON background_jobs (available_at, created_at) "
        "WHERE status = 'queued' AND locked_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_background_jobs_expired_lease "
        "ON background_jobs (locked_at, created_at) "
        "WHERE status = 'running'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_background_jobs_expired_lease")
    op.execute("DROP INDEX IF EXISTS ix_background_jobs_queued_claim")
