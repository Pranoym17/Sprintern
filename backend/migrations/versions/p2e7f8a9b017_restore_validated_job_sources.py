"""restore previously validated job sources to the database registry

Revision ID: p2e7f8a9b017
Revises: o1d6e7f8a906
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "p2e7f8a9b017"
down_revision: str | None = "o1d6e7f8a906"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOURCE_KEYS = (
    "vanshb03/Summer2027-Internships:README.md",
    "speedyapply/2027-SWE-College-Jobs:README.md",
    "speedyapply/2027-AI-College-Jobs:README.md",
    "sndsh404/summer-2027-internships:README.md",
    "zapplyjobs/Internships-2027:README.md",
    "zapplyjobs/Canada-Internships-2027:README.md",
    "zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships:README.md",
)


def upgrade() -> None:
    # These sources were validated and retained in the disaster-recovery TOML,
    # but the production database was created after configuration became the
    # runtime source of truth. Upsert them explicitly so new and existing
    # installations converge without resurrecting rejected repositories.
    op.execute(
        """
        INSERT INTO source_configurations (
            id, source, source_key, configuration, enabled, owner, repository,
            branch, path, poll_minutes, jitter_seconds, default_term,
            parser_schema, parser_version, created_at, updated_at
        )
        VALUES
            (
                'a824160f-e869-444a-af76-ddab6ab40004', 'github_repo',
                'vanshb03/Summer2027-Internships:README.md', '{}'::jsonb, true,
                'vanshb03', 'Summer2027-Internships', 'dev', 'README.md', 15, 30,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                '6b6ac258-1861-4cb4-b283-2ef27033de83', 'github_repo',
                'speedyapply/2027-SWE-College-Jobs:README.md', '{}'::jsonb, true,
                'speedyapply', '2027-SWE-College-Jobs', 'main', 'README.md', 180, 60,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                'e5544826-31d7-4d93-b26d-e5dc497bb54e', 'github_repo',
                'speedyapply/2027-AI-College-Jobs:README.md', '{}'::jsonb, true,
                'speedyapply', '2027-AI-College-Jobs', 'main', 'README.md', 180, 120,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                '1edb2252-c69b-414b-af94-259c0c765ff4', 'github_repo',
                'sndsh404/summer-2027-internships:README.md', '{}'::jsonb, true,
                'sndsh404', 'summer-2027-internships', 'main', 'README.md', 360, 240,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                '2165c051-7f4a-4387-8264-5c3cdb534cbb', 'github_repo',
                'zapplyjobs/Internships-2027:README.md',
                '{"disabled_reason":"upstream application links are placeholders"}'::jsonb,
                false,
                'zapplyjobs', 'Internships-2027', 'main', 'README.md', 60, 30,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                '5775ce3a-2229-4331-af61-f8100fc61366', 'github_repo',
                'zapplyjobs/Canada-Internships-2027:README.md',
                '{"disabled_reason":"upstream application links are placeholders"}'::jsonb,
                false,
                'zapplyjobs', 'Canada-Internships-2027', 'main', 'README.md', 60, 90,
                NULL, 'github_markdown_table', '1', now(), now()
            ),
            (
                '8787b64e-b269-4185-aca3-8710b88761e4', 'github_repo',
                'zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships:README.md',
                '{}'::jsonb, true, 'zshah101',
                'Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships',
                'main', 'README.md', 60, 150, NULL,
                'github_markdown_table', '1', now(), now()
            )
        ON CONFLICT (source, source_key) DO UPDATE
        SET enabled = EXCLUDED.enabled,
            configuration = EXCLUDED.configuration,
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
    keys = ", ".join(f"'{key}'" for key in SOURCE_KEYS)
    op.execute(
        "UPDATE source_configurations SET enabled = false, updated_at = now() "
        f"WHERE source = 'github_repo' AND source_key IN ({keys})"
    )
