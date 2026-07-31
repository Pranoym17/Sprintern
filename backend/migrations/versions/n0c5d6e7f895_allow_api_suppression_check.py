"""allow API role to check its authenticated user's email suppression

Revision ID: n0c5d6e7f895
Revises: m9b4c5d6e784
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "n0c5d6e7f895"
down_revision: str | None = "m9b4c5d6e784"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON email_suppressions TO sprintern_api")
    # The API only needs to answer whether the signed-in user's own address is
    # suppressed; provider event history and every other address remain internal.
    op.execute(
        """
        CREATE POLICY "email_suppressions_api_owner_read"
        ON email_suppressions
        FOR SELECT
        TO sprintern_api
        USING (
          EXISTS (
            SELECT 1
            FROM profiles AS profile
            WHERE profile.id = public.sprintern_auth_user_id()
              AND lower(profile.email) = lower(email_suppressions.email)
          )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        'DROP POLICY IF EXISTS "email_suppressions_api_owner_read" '
        "ON email_suppressions"
    )
    op.execute("REVOKE SELECT ON email_suppressions FROM sprintern_api")
