from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.orm.session import SessionTransaction

from api.auth.dependencies import get_current_user
from api.auth.models import AuthenticatedUser
from api.settings import settings

worker_url = settings.database_worker_url or settings.database_url
api_url = settings.database_api_url or settings.database_url

engine = create_engine(worker_url, pool_pre_ping=True)
api_engine = create_engine(api_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
ApiSessionLocal = sessionmaker(bind=api_engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def apply_rls_claim(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    subject = session.info.get("authenticated_user_id")
    if subject:
        connection.exec_driver_sql(
            "SELECT set_config('request.jwt.claim.sub', %s, true)",
            (str(subject),),
        )


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def get_user_db(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Generator[Session]:
    """Set transaction-local claims so PostgreSQL RLS independently enforces ownership."""
    with ApiSessionLocal() as session:
        session.info["authenticated_user_id"] = user.id
        yield session
