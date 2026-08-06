"""reduce large source polling

Revision ID: t6c1d2e3f451
Revises: s5b0c1d2e340
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "t6c1d2e3f451"
down_revision: str | None = "s5b0c1d2e340"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_configurations
        SET poll_minutes = 30, jitter_seconds = 0, updated_at = now()
        WHERE source = 'github_repo'
          AND source_key = 'SimplifyJobs/Summer2027-Internships:README.md'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE source_configurations
        SET poll_minutes = 10, jitter_seconds = 0, updated_at = now()
        WHERE source = 'github_repo'
          AND source_key = 'SimplifyJobs/Summer2027-Internships:README.md'
        """
    )
