"""harden application tracker

Revision ID: c9d4e5f6a704
Revises: b8c3d4e5f603
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d4e5f6a704"
down_revision: str | Sequence[str] | None = "b8c3d4e5f603"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX ix_applications_profile_import_key "
        "ON applications(profile_id, import_key) WHERE import_key IS NOT NULL"
    )
    op.create_index(
        "ix_application_events_profile_created",
        "application_events",
        ["profile_id", "created_at"],
    )
    op.create_index("ix_applications_profile_applied", "applications", ["profile_id", "applied_at"])


def downgrade() -> None:
    op.drop_index("ix_applications_profile_applied", table_name="applications")
    op.drop_index("ix_application_events_profile_created", table_name="application_events")
    op.drop_index("ix_applications_profile_import_key", table_name="applications")
