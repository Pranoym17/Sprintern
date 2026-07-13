import uuid
from collections.abc import AsyncIterator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser, get_current_user
from api.database import engine, get_db
from api.main import app


@pytest.fixture
def db_session() -> Generator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(id=uuid.uuid4(), email="student@example.com")


@pytest.fixture
async def api_client(
    db_session: Session, authenticated_user: AuthenticatedUser
) -> AsyncIterator[AsyncClient]:
    def override_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
