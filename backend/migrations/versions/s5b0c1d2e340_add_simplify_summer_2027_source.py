"""add Simplify Summer 2027 source

Revision ID: s5b0c1d2e340
Revises: r4a9b0c1d239
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "s5b0c1d2e340"
down_revision: str | None = "r4a9b0c1d239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The database registry is authoritative at runtime; the TOML entry remains
    # the bootstrap and recovery fallback for a fresh environment.
    op.execute(
        """
        INSERT INTO source_configurations (
            id, source, source_key, configuration, enabled, owner, repository,
            branch, path, poll_minutes, jitter_seconds, default_term,
            parser_schema, parser_version, created_at, updated_at
        )
        VALUES (
            'c19b76fb-d891-4705-af0c-04e22bf24e77', 'github_repo',
            'SimplifyJobs/Summer2027-Internships:README.md',
            '{}'::jsonb, true, 'SimplifyJobs', 'Summer2027-Internships',
            'dev', 'README.md', 10, 0, 'Summer 2027',
            'github_html_table', '1', now(), now()
        )
        ON CONFLICT (source, source_key) DO UPDATE
        SET enabled = true,
            owner = EXCLUDED.owner,
            repository = EXCLUDED.repository,
            branch = EXCLUDED.branch,
            path = EXCLUDED.path,
            poll_minutes = EXCLUDED.poll_minutes,
            jitter_seconds = EXCLUDED.jitter_seconds,
            default_term = EXCLUDED.default_term,
            parser_schema = EXCLUDED.parser_schema,
            parser_version = EXCLUDED.parser_version,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM source_configurations
        WHERE source = 'github_repo'
          AND source_key = 'SimplifyJobs/Summer2027-Internships:README.md'
        """
    )
