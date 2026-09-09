"""Test fixtures.

Tests run against a SEPARATE database (`<db>_test`) created here and dropped
at the end of the session, so running the suite can never touch development
data. Schema is built with Base.metadata.create_all rather than by running the
migrations: `alembic check` already proves the migration and the models agree,
so re-running migrations per session would only add time.
"""

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Import the models package so Base.metadata is fully populated before
# create_all - an unimported model is silently missing from the schema.
#
# `from app import models`, never `import app.models`: the latter rebinds the
# name `app` in this module from the FastAPI instance to the package, and
# app.dependency_overrides then resolves against the module.
from app import models as _models  # noqa: F401
from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app

settings = get_settings()
TEST_DB_NAME = f"{settings.postgres_db}_test"


def _admin_url() -> str:
    """URL for the maintenance database, used to CREATE/DROP the test DB.
    CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT below."""
    return (
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )


def _test_db_url() -> str:
    return (
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{TEST_DB_NAME}"
    )


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        # Drop first: a suite killed mid-run leaves the DB behind, and a stale
        # schema would make the next run fail confusingly.
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))

    test_engine = create_engine(_test_db_url(), pool_pre_ping=True)
    Base.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """A session whose work is rolled back after every test.

    join_transaction_mode="create_savepoint" makes the application's own
    db.commit() calls release a SAVEPOINT instead of committing the outer
    transaction, so endpoints run their real commit path while the test still
    ends with a clean database.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient with the app's DB dependency pointed at the test session."""

    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def unique_email() -> str:
    """Fresh address per call, so tests never collide on the UNIQUE index.

    NOT a .test/.local/.invalid domain: email-validator rejects RFC 6761
    special-use TLDs outright, which would fail every signup here for a reason
    that has nothing to do with the code under test.
    """
    return f"user-{uuid.uuid4().hex[:12]}@levelforge.dev"


@pytest.fixture
def user_factory(client: TestClient):
    """Create a signed-up user and return (headers, payload)."""

    def _make(timezone: str = "UTC", password: str = "correct-horse-1") -> tuple[dict, dict]:
        email = unique_email()
        signup = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": password,
                "display_name": "Tester",
                "timezone": timezone,
            },
        )
        assert signup.status_code == 201, signup.text
        login = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, signup.json()

    return _make


@pytest.fixture
def auth(user_factory) -> dict:
    headers, _ = user_factory()
    return headers
