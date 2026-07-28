"""add validated 2027 sources

Revision ID: m9b4c5d6e784
Revises: l8a3b4c5d673
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m9b4c5d6e784"
down_revision: str | None = "l8a3b4c5d673"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This repository keeps its historical name, but current listings moved to
    # a dedicated 2027 file. Retire the old identity before inserting the new one.
    op.execute(
        """
        UPDATE source_configurations
        SET enabled = false, updated_at = now()
        WHERE source = 'github_repo'
          AND lower(owner) = 'negarprh'
          AND lower(repository) = 'canadian-tech-internships-2026'
          AND path != 'README-2027.md'
        """
    )
    op.execute(
        """
        INSERT INTO source_configurations (
            id, source, source_key, configuration, enabled, owner, repository,
            branch, path, poll_minutes, jitter_seconds, default_term,
            parser_schema, parser_version, created_at, updated_at
        )
        VALUES
            (
                'fd0a64b9-958f-4af6-a0ed-951d07611451', 'github_repo',
                'negarprh/Canadian-Tech-Internships-2026:README-2027.md',
                '{}'::jsonb, true, 'negarprh', 'Canadian-Tech-Internships-2026',
                'main', 'README-2027.md', 90, 300, NULL,
                'github_markdown_table', '1', now(), now()
            ),
            (
                'ba9f8d6e-e277-4b7b-87b0-45ec5bdbeaa3', 'github_repo',
                'hanzili/canada_sde_intern_position:README.md',
                '{}'::jsonb, true, 'hanzili', 'canada_sde_intern_position',
                'main', 'README.md', 60, 210, NULL,
                'github_markdown_table', '1', now(), now()
            ),
            (
                '90df17d4-3287-4f87-860e-23115d7ec21d', 'github_repo',
                'ApplyGuy/2027-Internships:README.md',
                '{}'::jsonb, true, 'ApplyGuy', '2027-Internships',
                'main', 'README.md', 60, 270, NULL,
                'github_markdown_table', '1', now(), now()
            )
        ON CONFLICT (source, source_key) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            owner = EXCLUDED.owner,
            repository = EXCLUDED.repository,
            branch = EXCLUDED.branch,
            path = EXCLUDED.path,
            poll_minutes = EXCLUDED.poll_minutes,
            jitter_seconds = EXCLUDED.jitter_seconds,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM source_configurations
        WHERE source = 'github_repo'
          AND source_key IN (
            'negarprh/Canadian-Tech-Internships-2026:README-2027.md',
            'hanzili/canada_sde_intern_position:README.md',
            'ApplyGuy/2027-Internships:README.md'
          )
        """
    )
