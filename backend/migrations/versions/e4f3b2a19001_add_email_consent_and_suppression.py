"""add email consent and suppression

Revision ID: e4f3b2a19001
Revises: c18f4a92d761
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f3b2a19001"
down_revision: str | Sequence[str] | None = "c18f4a92d761"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("email_notifications_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "profiles", sa.Column("email_suppressed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "profiles", sa.Column("email_suppression_reason", sa.String(length=32), nullable=True)
    )
    # Existing accounts never explicitly consented under the new policy.
    op.execute("UPDATE profiles SET email_notifications_enabled = false")
    op.alter_column("profiles", "email_notifications_enabled", server_default=sa.text("false"))
    op.create_table(
        "email_suppressions",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="resend", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("email"),
    )
    op.create_table(
        "email_provider_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("email_provider_events")
    op.drop_table("email_suppressions")
    op.drop_column("profiles", "email_suppression_reason")
    op.drop_column("profiles", "email_suppressed_at")
    op.drop_column("profiles", "email_notifications_consent_at")
    op.alter_column("profiles", "email_notifications_enabled", server_default=sa.text("true"))
