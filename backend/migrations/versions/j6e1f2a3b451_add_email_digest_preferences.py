"""add email digest preferences

Revision ID: j6e1f2a3b451
Revises: i5d0e1f2a340
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j6e1f2a3b451"
down_revision: str | None = "i5d0e1f2a340"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "preferred_email_time",
            sa.Time(),
            nullable=False,
            server_default=sa.text("'08:00:00'"),
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "email_digest_job_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("7"),
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "email_empty_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_check_constraint(
        "ck_profiles_email_digest_job_limit",
        "profiles",
        "email_digest_job_limit BETWEEN 1 AND 10",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_profiles_email_digest_job_limit", "profiles", type_="check"
    )
    op.drop_column("profiles", "email_empty_digest_enabled")
    op.drop_column("profiles", "email_digest_job_limit")
    op.drop_column("profiles", "preferred_email_time")
