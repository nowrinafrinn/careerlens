"""Test setup.

- Tests run against a real Postgres database (careerlens_test), never SQLite,
  because constraints and JSONB behave differently there.
- The schema is built by running the real Alembic migrations once per test
  session, so the migrations themselves are tested on every run.
- Each test runs inside a transaction that is rolled back afterwards, so tests
  can't leak data into each other. Service code may call commit(); with
  join_transaction_mode="create_savepoint" that only releases a savepoint.
"""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db import get_db
from app.main import app


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    config = alembic_config(url)
    # Start from an empty schema each run, then migrate forward to head.
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
