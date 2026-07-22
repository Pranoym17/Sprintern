import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.models import MatchStatus
from api.rate_limiting import user_rate_limit
from api.repositories.matches import get_match, list_matches, match_status_counts
from api.repositories.pagination import decode_cursor, encode_cursor
from api.schemas import MatchPage, MatchResponse, MatchUpdate
from api.schemas.match import MatchCounts

router = APIRouter(prefix="/matches", tags=["matches"])
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=MatchPage)
def read_matches(
    user: CurrentUser,
    session: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
    status_filter: Annotated[MatchStatus | None, Query(alias="status")] = None,
    query: Annotated[str, Query(max_length=120)] = "",
    sort: Literal["newest", "company", "relevance", "deadline"] = "newest",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    collection: Literal[
        "toronto", "remote", "canadian", "new-week", "closing-soon", "reopened",
        "followed-companies", "strongest",
        "recently-viewed",
    ] | None = None,
    include_hidden: bool = False,
) -> MatchPage:
    if cursor and cursor.isdigit():
        page = int(cursor)
        decoded_cursor = None
    else:
        decoded_cursor = decode_cursor(cursor) if cursor else None
    matches = list_matches(
        session,
        user.id,
        limit,
        decoded_cursor,
        status_filter,
        query,
        sort,
        page,
        collection,
        include_hidden,
    )
    has_more = len(matches) > limit
    items = matches[:limit]
    next_cursor = (
        encode_cursor(items[-1].created_at, items[-1].id)
        if has_more and page == 1 and not query and sort == "newest" and collection is None
        else str(page + 1) if has_more else None
    )
    all_count, matched, applied, dismissed = match_status_counts(session, user.id)
    return MatchPage(
        items=[MatchResponse.model_validate(match) for match in items],
        next_cursor=next_cursor,
        counts=MatchCounts(all=all_count, matched=matched, applied=applied, dismissed=dismissed),
    )


@router.get("/{match_id}", response_model=MatchResponse)
def read_match(match_id: uuid.UUID, user: CurrentUser, session: Database) -> object:
    match = get_match(session, user.id, match_id)
    if match is None:
        raise AppError(404, "not_found", "Match not found")
    return match


@router.patch(
    "/{match_id}",
    response_model=MatchResponse,
    dependencies=[Depends(user_rate_limit("matches.update", 60))],
)
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
