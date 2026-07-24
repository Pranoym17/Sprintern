import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from api.models import JobSourceName, SourceConfiguration
from api.scheduler.config import GitHubSourceConfig, SchedulerSourceConfig, load_source_config

logger = logging.getLogger(__name__)


def _runtime_config(row: SourceConfiguration) -> GitHubSourceConfig:
    return GitHubSourceConfig(
        enabled=row.enabled,
        owner=row.owner,
        repository=row.repository,
        path=row.path,
        branch=row.branch,
        term=row.default_term,
        poll_minutes=row.poll_minutes,
        jitter_seconds=row.jitter_seconds,
    )


def seed_source_configurations(session: Session, fallback_path: str | Path) -> int:
    if session.scalar(select(func.count(SourceConfiguration.id))):
        return 0
    seeded = 0
    for source in load_source_config(fallback_path).github:
        session.add(
            SourceConfiguration(
                source=JobSourceName.GITHUB_REPO,
                source_key=source.source_key,
                configuration={},
                enabled=source.enabled,
                owner=source.owner,
                repository=source.repository,
                branch=source.branch,
                path=source.path,
                poll_minutes=source.poll_minutes,
                jitter_seconds=source.jitter_seconds,
                default_term=source.term,
            )
        )
        seeded += 1
    session.commit()
    return seeded


def load_runtime_source_config(
    session_factory: sessionmaker[Session], fallback_path: str | Path
) -> SchedulerSourceConfig:
    try:
        with session_factory() as session:
            seed_source_configurations(session, fallback_path)
            rows = list(
                session.scalars(
                    select(SourceConfiguration).order_by(SourceConfiguration.source_key)
                )
            )
            return SchedulerSourceConfig(github=[_runtime_config(row) for row in rows])
    except (SQLAlchemyError, OSError, ValueError) as exc:
        logger.warning(
            "scheduler.sources.database_fallback",
            extra={
                "event": "scheduler.sources.database_fallback",
                "exception_class": type(exc).__name__,
            },
        )
        return load_source_config(fallback_path)
