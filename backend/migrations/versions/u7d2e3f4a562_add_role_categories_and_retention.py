"""add role categories and retention

Revision ID: u7d2e3f4a562
Revises: t6c1d2e3f451
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "u7d2e3f4a562"
down_revision: str | None = "t6c1d2e3f451"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "filters",
        sa.Column(
            "role_categories",
            sa.ARRAY(sa.String(length=48)),
            nullable=False,
            server_default=sa.text("'{all}'::varchar[]"),
        ),
    )
    # Preserve the intent of existing free-form filters during the one-way
    # taxonomy migration. Unknown old phrases become Other technical rather
    # than silently widening a user's alerts to every role.
    op.execute(
        """
        UPDATE filters AS f
        SET role_categories = CASE
          WHEN cardinality(f.role_keywords) = 0
            OR EXISTS (
              SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
              WHERE lower(keyword.value) IN ('all', 'any', 'any role', 'any role or field')
            )
            THEN ARRAY['all']::varchar[]
          ELSE COALESCE(
            NULLIF(array_remove(ARRAY[
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~
                  '(software|swe|sde|backend|front.?end|full.?stack|mobile|qa|test)'
              ) THEN 'software_engineering' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~ (
                  '(data|machine learning|ml|artificial intelligence|(^|[^a-z])'
                  || 'ai([^a-z]|$)|research|vision|nlp'
                )
              ) THEN 'ai_ml_data' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~
                  '(cloud|devops|sre|infrastructure|systems|network|security)'
              ) THEN 'cloud_infrastructure_security' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~
                  '(embedded|firmware|hardware|electrical|asic|fpga|silicon|verification|mechanical|robotics)'
              ) THEN 'hardware_embedded_silicon' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~ '(product|design|ux|ui|research)'
              ) THEN 'product_design_research' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~ '(quant|trading)'
              ) THEN 'quant_finance' END,
              CASE WHEN EXISTS (
                SELECT 1 FROM unnest(f.role_keywords) AS keyword(value)
                WHERE lower(keyword.value) ~
                  '(business|marketing|sales|operations|consulting|recruit|finance|risk|hr)'
              ) THEN 'business_operations_people' END
            ]::varchar[], NULL), '{}'::varchar[]),
            ARRAY['other_technical']::varchar[]
          )
        END
        """
    )
    op.create_check_constraint(
        "ck_filters_role_categories",
        "filters",
        """
        cardinality(role_categories) BETWEEN 1 AND 5
        AND role_categories <@ ARRAY[
          'all', 'software_engineering', 'ai_ml_data',
          'cloud_infrastructure_security', 'hardware_embedded_silicon',
          'product_design_research', 'quant_finance',
          'business_operations_people', 'other_technical'
        ]::varchar[]
        AND NOT ('all' = ANY(role_categories) AND cardinality(role_categories) > 1)
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_filters_role_categories", "filters", type_="check")
    op.drop_column("filters", "role_categories")
