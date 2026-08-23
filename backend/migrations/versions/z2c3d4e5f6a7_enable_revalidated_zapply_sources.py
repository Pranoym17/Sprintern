"""enable revalidated Zapply internship sources

Revision ID: z2c3d4e5f6a7
Revises: y1b2c3d4e5f6
Create Date: 2026-08-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "z2c3d4e5f6a7"
down_revision: str | None = "y1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = (
    ("57c44ec0-b8de-4d27-a426-4cfd6afdbe50", "Internships-2027"),
    ("1e9a54a4-8e82-448f-934f-af4ddc0d197d", "Canada-Internships-2027"),
)


def upgrade() -> None:
    # Both repositories now expose direct employer application URLs. Enable
    # them at a restrained cadence because they contain large full snapshots.
    for source_id, repository in SOURCES:
        source_key = f"zapplyjobs/{repository}:README.md"
        op.execute(
            "INSERT INTO source_configurations ("
            "id, source, source_key, configuration, enabled, owner, repository, "
            "branch, path, poll_minutes, jitter_seconds, default_term, "
            "parser_schema, parser_version, created_at, updated_at"
            ") VALUES ("
            f"'{source_id}', 'github_repo', '{source_key}', '{{}}'::jsonb, true, "
            f"'zapplyjobs', '{repository}', 'main', 'README.md', 30, 0, NULL, "
            "'github_markdown_table', '1', now(), now()"
            ") ON CONFLICT (source, source_key) DO UPDATE SET "
            "enabled = EXCLUDED.enabled, owner = EXCLUDED.owner, "
            "repository = EXCLUDED.repository, branch = EXCLUDED.branch, "
            "path = EXCLUDED.path, poll_minutes = EXCLUDED.poll_minutes, "
            "jitter_seconds = EXCLUDED.jitter_seconds, updated_at = now()"
        )


def downgrade() -> None:
    for _, repository in SOURCES:
        source_key = f"zapplyjobs/{repository}:README.md"
        op.execute(
            "UPDATE source_configurations "
            "SET enabled = false, poll_minutes = 60, updated_at = now() "
            "WHERE source = 'github_repo' "
            f"AND source_key = '{source_key}'"
        )
