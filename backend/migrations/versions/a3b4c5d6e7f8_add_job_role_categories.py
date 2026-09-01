"""add persisted job role categories

Revision ID: a3b4c5d6e7f8
Revises: z2c3d4e5f6a7
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "z2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "role_categories",
            sa.ARRAY(sa.String(length=48)),
            nullable=False,
            server_default=sa.text("'{other_technical}'::varchar[]"),
        ),
    )
    # Use the same deliberately broad title signals as the matcher. A role can
    # belong to more than one group; unrecognised titles remain discoverable
    # through Other technical instead of disappearing from the board.
    op.execute(
        """
        UPDATE jobs
        SET role_categories = COALESCE(
          NULLIF(array_remove(ARRAY[
            CASE WHEN lower(title) ~ (
              '(software|swe|sde|developer|front.?end|back.?end|full.?stack|mobile|qa|test)'
            ) THEN 'software_engineering' END,
            CASE WHEN lower(title) ~ (
              '(data|machine learning|(^|[^a-z])ml([^a-z]|$)|artificial intelligence|'
              || '(^|[^a-z])ai([^a-z]|$)|research|vision|nlp)'
            ) THEN 'ai_ml_data' END,
            CASE WHEN lower(title) ~ (
              '(cloud|devops|sre|infrastructure|systems|network|security)'
            ) THEN 'cloud_infrastructure_security' END,
            CASE WHEN lower(title) ~ (
              '(embedded|firmware|hardware|electrical|asic|fpga|silicon|verification|mechanical|robotics)'
            ) THEN 'hardware_embedded_silicon' END,
            CASE WHEN lower(title) ~ (
              '(product|design|ux|ui|research)'
            ) THEN 'product_design_research' END,
            CASE WHEN lower(title) ~ (
              '(quant|trading|finance|risk)'
            ) THEN 'quant_finance' END,
            CASE WHEN lower(title) ~ (
              '(business|marketing|sales|operations|consulting|recruit|human resources|hr)'
            ) THEN 'business_operations_people' END
          ]::varchar[], NULL), '{}'::varchar[]),
          ARRAY['other_technical']::varchar[]
        )
        """
    )
    op.create_index(
        "ix_jobs_role_categories",
        "jobs",
        ["role_categories"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_role_categories", table_name="jobs")
    op.drop_column("jobs", "role_categories")
