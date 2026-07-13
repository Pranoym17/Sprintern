import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.models import Profile


def get_or_create_profile(session: Session, profile_id: uuid.UUID, email: str | None) -> Profile:
    statement = (
        insert(Profile)
        .values(id=profile_id, email=email)
        .on_conflict_do_update(index_elements=[Profile.id], set_={"email": email})
        .returning(Profile)
    )
    profile = session.execute(statement).scalar_one()
    session.commit()
    return profile


def get_profile(session: Session, profile_id: uuid.UUID) -> Profile | None:
    return session.get(Profile, profile_id)
