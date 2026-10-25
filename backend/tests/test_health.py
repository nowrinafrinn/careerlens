from collections.abc import Iterator

from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.main import app
from tests.conftest import alembic_config


def test_health_reports_database_and_current_migration(client: TestClient) -> None:
    head = ScriptDirectory.from_config(alembic_config(get_settings().test_database_url)).get_current_head()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "migration_revision": head}


def test_health_returns_503_when_database_is_unreachable() -> None:
    # Nothing listens on port 1. The short timeout keeps the test fast on
    # machines where the connection attempt hangs instead of being refused.
    dead_engine = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )

    def unreachable_db() -> Iterator[Session]:
        with Session(bind=dead_engine) as session:
            yield session

    app.dependency_overrides[get_db] = unreachable_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
        dead_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable", "migration_revision": None}


def test_unknown_route_uses_standard_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found", "details": None}}


def test_wrong_method_uses_standard_error_format(client: TestClient) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
