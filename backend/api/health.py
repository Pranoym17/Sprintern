import logging
from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.errors import AppError

logger = logging.getLogger(__name__)


@lru_cache
def expected_migration_revisions() -> set[str]:
    return set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())


def assert_ready(session: Session) -> None:
    """Prove the database responds and is at the code's migration head."""
    try:
        session.execute(text("SELECT 1"))
        current = set(session.scalars(text("SELECT version_num FROM alembic_version")))
        if current != expected_migration_revisions():
            raise RuntimeError("database migration revision does not match application head")
    except Exception as exc:
        logger.warning(
            "health.readiness.failed",
            extra={"event": "health.readiness.failed", "exception_class": type(exc).__name__},
        )
        raise AppError(503, "not_ready", "Service is not ready") from exc
