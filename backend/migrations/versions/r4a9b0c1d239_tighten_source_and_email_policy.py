"""tighten source schedule and email channel policy

Revision ID: r4a9b0c1d239
Revises: q3f8a9b0c128
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "r4a9b0c1d239"
down_revision: str | None = "q3f8a9b0c128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Database rows are the runtime source of truth. Exact intervals avoid the
    # surprise of jitter stretching a requested ten-minute refresh to fifteen.
    op.execute(
        """
        UPDATE source_configurations
        SET poll_minutes = 10, jitter_seconds = 0, updated_at = now()
        WHERE source = 'github_repo' AND enabled = true
        """
    )
    op.alter_column("source_configurations", "poll_minutes", server_default="10")
    op.alter_column("source_configurations", "jitter_seconds", server_default="0")

    # Fail closed for deliveries created before email became digest-only.
    op.execute(
        """
        UPDATE notification_deliveries
        SET status = 'cancelled', next_attempt_at = NULL,
            last_error = 'Email is limited to the daily job digest', updated_at = now()
        WHERE channel = 'email'
          AND notification_type != 'new_match'
          AND status IN ('pending', 'failed')
        """
    )
    op.execute(
        """
        UPDATE profiles
        SET email_empty_digest_enabled = false, updated_at = now()
        WHERE email_empty_digest_enabled = true
        """
    )


def downgrade() -> None:
    op.alter_column("source_configurations", "poll_minutes", server_default="15")
    op.alter_column("source_configurations", "jitter_seconds", server_default="30")
