from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import require_internal_api_key
from api.database import get_db
from api.models import SourceState
from api.schemas import SourceStatusResponse

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_api_key)],
)
Database = Annotated[Session, Depends(get_db)]


@router.get("/sources/status", response_model=list[SourceStatusResponse])
def read_source_status(session: Database) -> object:
    return list(
        session.scalars(select(SourceState).order_by(SourceState.source, SourceState.source_key))
    )
