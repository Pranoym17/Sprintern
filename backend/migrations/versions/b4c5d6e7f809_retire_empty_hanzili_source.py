"""retire empty Hanzili internship source

Revision ID: b4c5d6e7f809
Revises: a3b4c5d6e7f8
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4c5d6e7f809"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_KEY = "hanzili/canada_sde_intern_position:README.md"


def upgrade() -> None:
    # The upstream README currently has empty category placeholders rather than
    # job rows and original employer application links. Disable it so workers do
    # not repeatedly fail, then clear the operator-facing failure state.
    op.execute(
        "UPDATE source_configurations "
        "SET enabled = false, poll_minutes = 60, updated_at = now() "
        "WHERE source = 'github_repo' "
        f"AND source_key = '{SOURCE_KEY}'"
    )
    op.execute(
        "UPDATE source_states SET consecutive_failures = 0, backoff_until = NULL, "
        "last_error = NULL, last_succeeded_at = now(), updated_at = now() "
        "WHERE source = 'github_repo' "
        f"AND source_key = '{SOURCE_KEY}'"
    )
    op.execute(
        "UPDATE parser_alerts SET resolved_at = now() "
        f"WHERE source_key = '{SOURCE_KEY}' AND resolved_at IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE source_configurations "
        "SET enabled = true, poll_minutes = 30, updated_at = now() "
        "WHERE source = 'github_repo' "
        f"AND source_key = '{SOURCE_KEY}'"
    )
