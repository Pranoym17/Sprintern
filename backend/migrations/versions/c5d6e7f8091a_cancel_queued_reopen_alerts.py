"""cancel queued reopened-posting alerts

Revision ID: c5d6e7f8091a
Revises: b4c5d6e7f809
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d6e7f8091a"
down_revision: str | None = "b4c5d6e7f809"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These alerts were generated while source snapshots could briefly shrink.
    # Do not let old false-reopen deliveries crowd out new-match Telegram alerts.
    op.execute(
        "UPDATE notification_deliveries "
        "SET status = 'cancelled', next_attempt_at = NULL, "
        "last_error = 'Cancelled after reopened-posting lifecycle safeguard', "
        "updated_at = now() "
        "WHERE notification_type = 'posting_reopened' "
        "AND status IN ('pending', 'failed')"
    )


def downgrade() -> None:
    # Cancelled alerts are intentionally not revived during a rollback.
    pass
