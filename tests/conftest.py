from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from api.database import engine


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
