from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.repositories.matches import analytics_summary
from api.schemas import AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=AnalyticsSummary)
def read_summary(user: CurrentUser, session: Database) -> AnalyticsSummary:
    matched, applied, average = analytics_summary(session, user.id)
    return AnalyticsSummary(
        matched_count=matched,
        applied_count=applied,
        average_seconds_to_apply=average,
    )
