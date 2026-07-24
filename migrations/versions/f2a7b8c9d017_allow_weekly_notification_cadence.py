"""allow weekly notification cadence

Revision ID: f2a7b8c9d017
Revises: e1f6a7b8c906
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a7b8c9d017"
down_revision: str | Sequence[str] | None = "e1f6a7b8c906"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE profiles DROP CONSTRAINT notification_cadence")
    op.execute(
        "ALTER TABLE profiles ADD CONSTRAINT notification_cadence "
        "CHECK (notification_cadence IN ('instant', 'hourly', 'daily', 'weekly'))"
    )
    op.execute("ALTER TABLE notification_deliveries DROP CONSTRAINT delivery_cadence")
    op.execute(
        "ALTER TABLE notification_deliveries ADD CONSTRAINT delivery_cadence "
        "CHECK (cadence IN ('instant', 'hourly', 'daily', 'weekly'))"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE profiles SET notification_cadence = 'daily' WHERE notification_cadence = 'weekly'"
    )
    op.execute("UPDATE notification_deliveries SET cadence = 'daily' WHERE cadence = 'weekly'")
    op.execute("ALTER TABLE profiles DROP CONSTRAINT notification_cadence")
    op.execute(
        "ALTER TABLE profiles ADD CONSTRAINT notification_cadence "
        "CHECK (notification_cadence IN ('instant', 'hourly', 'daily'))"
    )
    op.execute("ALTER TABLE notification_deliveries DROP CONSTRAINT delivery_cadence")
    op.execute(
        "ALTER TABLE notification_deliveries ADD CONSTRAINT delivery_cadence "
        "CHECK (cadence IN ('instant', 'hourly', 'daily'))"
    )
