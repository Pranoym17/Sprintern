"""harden reopened posting alerts

Revision ID: d6e7f8091a2b
Revises: c5d6e7f8091a
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d6e7f8091a2b"
down_revision: str | None = "c5d6e7f8091a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical reopen markers were created before a full-expiry proof was
    # required. Do not continue presenting or sending those noisy alerts.
    op.execute("UPDATE jobs SET reopened_at = NULL WHERE reopened_at IS NOT NULL")
    op.execute(
        "UPDATE notification_deliveries "
        "SET status = 'cancelled', next_attempt_at = NULL, "
        "last_error = 'Cancelled: reopened posting was not lifecycle-verified', "
        "updated_at = now() "
        "WHERE notification_type = 'posting_reopened' "
        "AND status IN ('pending', 'failed')"
    )


def downgrade() -> None:
    # Historical markers and cancelled alerts cannot be reconstructed safely.
    pass
