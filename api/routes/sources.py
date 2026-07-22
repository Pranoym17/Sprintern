from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.models import JobSourceName, SourceState
from api.scheduler.config import load_source_config
from api.schemas.source import PublicSourceStatus
from api.settings import settings

router = APIRouter(prefix="/sources", tags=["sources"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/status", response_model=PublicSourceStatus)
def read_public_source_status(_user: CurrentUser, session: Database) -> PublicSourceStatus:
    """Expose aggregate freshness without operational source details."""
    try:
        configured_keys = {
            source.source_key
            for source in load_source_config(settings.scheduler_source_config).enabled_github
        }
    except ValueError:
        return PublicSourceStatus(state="unknown", last_updated_at=None)
    rows = session.scalars(
        select(SourceState).where(
            SourceState.source == JobSourceName.GITHUB_REPO,
            SourceState.source_key.in_(configured_keys),
        )
    )
    successes = {row.source_key: row.last_succeeded_at for row in rows if row.last_succeeded_at}
    if not successes:
        return PublicSourceStatus(state="unknown", last_updated_at=None)
    last_updated_at = max(successes.values())
    stale_before = datetime.now(UTC) - timedelta(hours=settings.source_stale_after_hours)
    all_fresh = configured_keys == successes.keys() and all(
        succeeded_at >= stale_before for succeeded_at in successes.values()
    )
    return PublicSourceStatus(
        state="healthy" if all_fresh else "stale",
        last_updated_at=last_updated_at,
    )
