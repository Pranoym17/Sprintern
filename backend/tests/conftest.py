import uuid
from collections.abc import AsyncIterator, Generator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser, get_current_user
from api.database import engine, get_db, get_user_db
from api.main import app


class VersionedASGITransport(httpx.AsyncBaseTransport):
    """Keep endpoint tests concise while exercising only the versioned public contract."""

    def __init__(self) -> None:
        self._transport = ASGITransport(app=app)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/internal/"):
            path = f"/internal/v1{path.removeprefix('/internal')}"
        elif path not in {"/health", "/health/live", "/health/ready"}:
            path = f"/api/v1{path}"
        request.url = request.url.copy_with(path=path)
        return await self._transport.handle_async_request(request)


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
    app.dependency_overrides[get_user_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    async with AsyncClient(transport=VersionedASGITransport(), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
