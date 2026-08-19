"""replace removed Canadian internship source

Revision ID: y1b2c3d4e5f6
Revises: x0a1b2c3d4e5
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "y1b2c3d4e5f6"
down_revision: str | None = "x0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMOVED_SOURCE_KEY = "negarprh/Canadian-Tech-Internships-2026:README-2027.md"
REPLACEMENT_SOURCE_KEY = "michelleokolie/canada-tech-internships-summer-2027:README.md"


def upgrade() -> None:
    # The old README was removed upstream and now returns a real GitHub 404.
    # Disable it rather than repeatedly consuming worker capacity and alerting
    # the operator for an unrecoverable external condition.
    op.execute(
        "UPDATE source_configurations SET enabled = false, updated_at = now() "
        f"WHERE source = 'github_repo' AND source_key = '{REMOVED_SOURCE_KEY}'"
    )
    op.execute(
        "UPDATE source_states SET consecutive_failures = 0, backoff_until = NULL, "
        "last_error = NULL, last_succeeded_at = now(), updated_at = now() "
        f"WHERE source = 'github_repo' AND source_key = '{REMOVED_SOURCE_KEY}'"
    )
    op.execute(
        "UPDATE parser_alerts SET resolved_at = now() "
        f"WHERE source_key = '{REMOVED_SOURCE_KEY}' AND resolved_at IS NULL"
    )
    op.execute(
        "INSERT INTO source_configurations ("
        "id, source, source_key, configuration, enabled, owner, repository, "
        "branch, path, poll_minutes, jitter_seconds, default_term, "
        "parser_schema, parser_version, created_at, updated_at"
        ") VALUES ("
        "'32fa385a-ee63-4abe-956c-1a82e68c7692', 'github_repo', "
        f"'{REPLACEMENT_SOURCE_KEY}', '{{}}'::jsonb, true, "
        "'michelleokolie', 'canada-tech-internships-summer-2027', "
        "'main', 'README.md', 30, 0, 'Summer 2027', "
        "'github_markdown_table', '1', now(), now()"
        ") ON CONFLICT (source, source_key) DO UPDATE SET "
        "enabled = EXCLUDED.enabled, owner = EXCLUDED.owner, "
        "repository = EXCLUDED.repository, branch = EXCLUDED.branch, "
        "path = EXCLUDED.path, poll_minutes = EXCLUDED.poll_minutes, "
        "jitter_seconds = EXCLUDED.jitter_seconds, default_term = EXCLUDED.default_term, "
        "updated_at = now()"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM source_configurations "
        f"WHERE source = 'github_repo' AND source_key = '{REPLACEMENT_SOURCE_KEY}'"
    )
    op.execute(
        "UPDATE source_configurations SET enabled = true, updated_at = now() "
        f"WHERE source = 'github_repo' AND source_key = '{REMOVED_SOURCE_KEY}'"
    )
