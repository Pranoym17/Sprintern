"""allow the worker role to operate the durable queue

Revision ID: q3f8a9b0c128
Revises: p2e7f8a9b017
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "q3f8a9b0c128"
down_revision: str | None = "p2e7f8a9b017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # background_jobs was created after the original worker-policy table list.
    # Enabling RLS without this policy correctly blocked the scheduler and worker.
    op.execute(
        "CREATE POLICY background_jobs_worker_access ON background_jobs "
        "FOR ALL TO sprintern_worker USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS background_jobs_worker_access ON background_jobs")
