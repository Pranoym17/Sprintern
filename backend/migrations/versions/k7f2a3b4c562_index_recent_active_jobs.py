"""index recent active jobs

Revision ID: k7f2a3b4c562
Revises: j6e1f2a3b451
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "k7f2a3b4c562"
down_revision: str | None = "j6e1f2a3b451"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_jobs_status_first_seen", "jobs", ["status", "first_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_first_seen", table_name="jobs")
