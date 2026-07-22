"""expand notification controls

Revision ID: d0e5f6a7b805
Revises: c9d4e5f6a704
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e5f6a7b805"
down_revision: str | Sequence[str] | None = "c9d4e5f6a704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("quiet_hours_start", sa.Time(), nullable=True))
    op.add_column("profiles", sa.Column("quiet_hours_end", sa.Time(), nullable=True))
    op.add_column(
        "profiles", sa.Column("weekend_pause", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "profiles",
        sa.Column("max_alerts_per_day", sa.Integer(), server_default="25", nullable=False),
    )
    op.add_column(
        "profiles",
        sa.Column("priority_only_instant", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "notification_consents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("notification_deliveries", sa.Column("profile_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE notification_deliveries d SET profile_id = m.profile_id "
        "FROM matches m WHERE d.match_id = m.id"
    )
    op.alter_column("notification_deliveries", "profile_id", nullable=False)
    op.create_foreign_key(
        "fk_deliveries_profile",
        "notification_deliveries",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("notification_deliveries", "match_id", nullable=True)
    op.drop_constraint("uq_deliveries_match_channel", "notification_deliveries", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_deliveries_match_channel "
        "ON notification_deliveries(match_id, channel) "
        "WHERE match_id IS NOT NULL"
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("notification_type", sa.String(40), server_default="new_match", nullable=False),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("priority", sa.String(16), server_default="normal", nullable=False),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("notification_deliveries", sa.Column("queued_reason", sa.String(80)))
    op.create_index(
        "ix_deliveries_profile_status", "notification_deliveries", ["profile_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_deliveries_profile_status", table_name="notification_deliveries")
    op.drop_column("notification_deliveries", "queued_reason")
    op.drop_column("notification_deliveries", "payload")
    op.drop_column("notification_deliveries", "priority")
    op.drop_column("notification_deliveries", "notification_type")
    op.drop_index("uq_deliveries_match_channel", table_name="notification_deliveries")
    op.create_unique_constraint(
        "uq_deliveries_match_channel", "notification_deliveries", ["match_id", "channel"]
    )
    op.alter_column("notification_deliveries", "match_id", nullable=False)
    op.drop_constraint("fk_deliveries_profile", "notification_deliveries", type_="foreignkey")
    op.drop_column("notification_deliveries", "profile_id")
    op.drop_column("profiles", "notification_consents")
    op.drop_column("profiles", "priority_only_instant")
    op.drop_column("profiles", "max_alerts_per_day")
    op.drop_column("profiles", "weekend_pause")
    op.drop_column("profiles", "quiet_hours_end")
    op.drop_column("profiles", "quiet_hours_start")
