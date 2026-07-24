"""add source administration

Revision ID: e1f6a7b8c906
Revises: d0e5f6a7b805
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f6a7b8c906"
down_revision: str | Sequence[str] | None = "d0e5f6a7b805"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_configurations", sa.Column("owner", sa.String(100)))
    op.add_column("source_configurations", sa.Column("repository", sa.String(100)))
    op.add_column("source_configurations", sa.Column("branch", sa.String(255)))
    op.add_column(
        "source_configurations",
        sa.Column("path", sa.String(500), server_default="README.md", nullable=False),
    )
    op.add_column(
        "source_configurations",
        sa.Column("poll_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column(
        "source_configurations",
        sa.Column("jitter_seconds", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column("source_configurations", sa.Column("default_term", sa.String(100)))
    op.add_column(
        "source_configurations",
        sa.Column(
            "parser_schema",
            sa.String(64),
            server_default="github_markdown_table",
            nullable=False,
        ),
    )
    op.add_column(
        "source_configurations",
        sa.Column("parser_version", sa.String(32), server_default="1", nullable=False),
    )
    op.execute(
        "UPDATE source_configurations SET "
        "owner = COALESCE(configuration->>'owner', split_part(source_key, '/', 1)), "
        "repository = COALESCE(configuration->>'repository', "
        "split_part(split_part(source_key, '/', 2), ':', 1)), "
        "branch = configuration->>'branch', "
        "path = COALESCE(configuration->>'path', path), "
        "poll_minutes = COALESCE((configuration->>'poll_minutes')::integer, poll_minutes), "
        "jitter_seconds = COALESCE((configuration->>'jitter_seconds')::integer, jitter_seconds), "
        "default_term = configuration->>'term'"
    )
    op.alter_column("source_configurations", "owner", nullable=False)
    op.alter_column("source_configurations", "repository", nullable=False)
    op.create_table(
        "source_audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_configuration_id", sa.UUID()),
        sa.Column("administrator_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["source_configuration_id"], ["source_configurations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_audit_created", "source_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_source_audit_created", table_name="source_audit_logs")
    op.drop_table("source_audit_logs")
    for column in (
        "parser_version",
        "parser_schema",
        "default_term",
        "jitter_seconds",
        "poll_minutes",
        "path",
        "branch",
        "repository",
        "owner",
    ):
        op.drop_column("source_configurations", column)
