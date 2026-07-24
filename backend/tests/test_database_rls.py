import uuid

from sqlalchemy import text

from api.database import engine


def test_restricted_api_role_can_only_see_claimed_user() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    with engine.begin() as owner:
        owner.execute(
            text("INSERT INTO profiles (id, email) VALUES (:id, :email)"),
            [
                {"id": first_id, "email": "first-rls@example.test"},
                {"id": second_id, "email": "second-rls@example.test"},
            ],
        )
    try:
        with engine.begin() as restricted:
            restricted.execute(text("SET LOCAL ROLE sprintern_api"))
            restricted.execute(
                text("SELECT set_config('request.jwt.claim.sub', :subject, true)"),
                {"subject": str(first_id)},
            )
            visible = restricted.scalars(text("SELECT id FROM profiles ORDER BY id")).all()
            assert visible == [first_id]
            changed = restricted.execute(
                text("UPDATE profiles SET timezone = 'America/Toronto' WHERE id = :other"),
                {"other": second_id},
            )
            assert changed.rowcount == 0
    finally:
        with engine.begin() as owner:
            owner.execute(
                text("DELETE FROM profiles WHERE id IN (:first, :second)"),
                {"first": first_id, "second": second_id},
            )


def test_restricted_api_role_cannot_read_internal_tables() -> None:
    with engine.connect() as restricted:
        transaction = restricted.begin()
        try:
            restricted.execute(text("SET LOCAL ROLE sprintern_api"))
            try:
                restricted.execute(text("SELECT id FROM parser_alerts LIMIT 1"))
            except Exception as exc:
                assert "permission denied" in str(exc).casefold()
            else:
                raise AssertionError("API database role unexpectedly read an internal table")
        finally:
            transaction.rollback()


def test_worker_role_can_use_internal_tables_without_bypassing_rls() -> None:
    with engine.begin() as worker:
        worker.execute(text("SET LOCAL ROLE sprintern_worker"))
        worker.execute(text("SELECT id FROM parser_alerts LIMIT 1"))
        worker.execute(text("SELECT version_num FROM alembic_version"))
