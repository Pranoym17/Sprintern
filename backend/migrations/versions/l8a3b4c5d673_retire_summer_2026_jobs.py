"""retire summer 2026 jobs

Revision ID: l8a3b4c5d673
Revises: k7f2a3b4c562
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "l8a3b4c5d673"
down_revision: str | None = "k7f2a3b4c562"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_configurations
        SET enabled = false,
            updated_at = now()
        WHERE lower(coalesce(default_term, '')) = 'summer 2026'
           OR lower(coalesce(repository, '')) LIKE '%summer2026%'
           OR lower(coalesce(repository, '')) LIKE '%summer-2026%'
        """
    )
    op.execute(
        """
        UPDATE jobs
        SET status = 'expired',
            expired_at = coalesce(expired_at, now()),
            updated_at = now()
        WHERE lower(coalesce(term, '')) = 'summer 2026'
          AND status != 'expired'
        """
    )
    op.execute(
        """
        UPDATE notification_deliveries AS delivery
        SET status = 'cancelled',
            next_attempt_at = NULL,
            last_error = 'Summer 2026 posting retired',
            updated_at = now()
        FROM matches AS match, jobs AS job
        WHERE delivery.match_id = match.id
          AND match.job_id = job.id
          AND lower(coalesce(job.term, '')) = 'summer 2026'
          AND delivery.status IN ('pending', 'failed')
        """
    )


def downgrade() -> None:
    # Retiring time-sensitive listings is intentionally irreversible: a rollback
    # must not silently reactivate jobs or notifications that may now be closed.
    pass
