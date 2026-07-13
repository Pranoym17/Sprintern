from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.repositories.profiles import get_or_create_profile
from api.schemas import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/users", tags=["users"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=ProfileResponse)
def read_me(user: CurrentUser, session: Database) -> object:
    return get_or_create_profile(session, user.id, user.email)


@router.patch("/me", response_model=ProfileResponse)
def update_me(payload: ProfileUpdate, user: CurrentUser, session: Database) -> object:
    profile = get_or_create_profile(session, user.id, user.email)
    updates = payload.model_dump(exclude_unset=True)
    if (
        updates.get("timezone", "valid") is None
        or updates.get("notification_cadence", "valid") is None
    ):
        raise AppError(422, "validation_error", "Timezone and cadence cannot be null")
    for field, value in updates.items():
        setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return profile
