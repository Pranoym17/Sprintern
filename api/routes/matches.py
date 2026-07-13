import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.models import MatchStatus
from api.repositories.matches import get_match, list_matches
from api.repositories.pagination import decode_cursor, encode_cursor
from api.schemas import MatchPage, MatchResponse, MatchUpdate

router = APIRouter(prefix="/matches", tags=["matches"])
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=MatchPage)
def read_matches(
    user: CurrentUser,
    session: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> MatchPage:
    matches = list_matches(session, user.id, limit, decode_cursor(cursor) if cursor else None)
    has_more = len(matches) > limit
    items = matches[:limit]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    return MatchPage(
        items=[MatchResponse.model_validate(match) for match in items], next_cursor=next_cursor
    )


@router.get("/{match_id}", response_model=MatchResponse)
def read_match(match_id: uuid.UUID, user: CurrentUser, session: Database) -> object:
    match = get_match(session, user.id, match_id)
    if match is None:
        raise AppError(404, "not_found", "Match not found")
    return match


@router.patch("/{match_id}", response_model=MatchResponse)
def update_match(
    match_id: uuid.UUID, payload: MatchUpdate, user: CurrentUser, session: Database
) -> object:
    match = get_match(session, user.id, match_id)
    if match is None:
        raise AppError(404, "not_found", "Match not found")
    match.status = payload.status
    match.applied_at = datetime.now(UTC) if payload.status == MatchStatus.APPLIED else None
    session.commit()
    session.refresh(match)
    return match
