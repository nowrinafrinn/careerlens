from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE
from app.config import get_settings
from app.models import User, UserSession

PASSWORD = "correct horse battery"


def register(client: TestClient, email: str = "ada@example.com", password: str = PASSWORD, **extra):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password, **extra})


# --- registration -----------------------------------------------------------


def test_register_creates_account_and_signs_in(client: TestClient) -> None:
    response = register(client, email="  Ada@Example.COM ", display_name="Ada")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"  # trimmed and lowercased
    assert body["display_name"] == "Ada"
    assert body["ai_processing_consent_at"] is None
    assert "password" not in str(body).lower()

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_session_cookie_is_http_only_and_same_site_lax(client: TestClient) -> None:
    response = register(client)

    set_cookie = response.headers["set-cookie"].lower()
    assert set_cookie.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/" in set_cookie


def test_password_is_stored_as_argon2_hash(client: TestClient, db: Session) -> None:
    register(client)

    user = db.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2")
    assert PASSWORD not in user.password_hash


def test_session_token_is_stored_only_as_hash(client: TestClient, db: Session) -> None:
    register(client)
    token = client.cookies[SESSION_COOKIE]

    stored = db.scalars(select(UserSession.token_hash)).all()
    assert len(stored) == 1
    assert token not in stored
    assert len(stored[0]) == 64


def test_duplicate_email_is_rejected_case_insensitively(client: TestClient) -> None:
    register(client, email="ada@example.com")
    client.cookies.clear()

    response = register(client, email="ADA@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "not-an-email", "password": PASSWORD}, "email"),
        ({"email": "ada@example.com", "password": "short"}, "password"),
        ({"email": "ada@example.com", "password": "x" * 129}, "password"),
    ],
)
def test_invalid_registration_is_rejected(client: TestClient, payload: dict, field: str) -> None:
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(detail["loc"][-1] == field for detail in error["details"])


def test_validation_errors_do_not_echo_the_password(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": "bad", "password": "secret-but-short"[:7]})

    assert response.status_code == 422
    assert "secret-" not in response.text


def test_registration_can_be_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "allow_registration", False)

    response = register(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "registration_closed"


# --- login ------------------------------------------------------------------


def test_login_with_correct_password_signs_in(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post("/api/v1/auth/login", json={"email": "ADA@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_wrong_password_and_unknown_email_give_identical_errors(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    wrong_password = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope-nope"})
    unknown_email = client.post("/api/v1/auth/login", json={"email": "who@example.com", "password": PASSWORD})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert SESSION_COOKIE not in client.cookies


def test_logging_in_again_replaces_the_previous_session(client: TestClient, db: Session) -> None:
    register(client)
    first_token = client.cookies[SESSION_COOKIE]

    client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})

    assert client.cookies[SESSION_COOKIE] != first_token
    assert len(db.scalars(select(UserSession)).all()) == 1  # the old session row was deleted


# --- current user / logout / expiry -------------------------------------------


def test_me_without_session_is_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_with_made_up_token_is_401(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "forged-token")

    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_revokes_the_session_on_the_server(client: TestClient) -> None:
    register(client)
    token = client.cookies[SESSION_COOKIE]

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204

    # Replaying the old cookie must fail: the session is gone, not just the cookie.
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_when_signed_out_is_harmless(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_expired_session_is_rejected(client: TestClient, db: Session) -> None:
    register(client)
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))

    assert client.get("/api/v1/auth/me").status_code == 401


# --- isolation baseline ---------------------------------------------------------


def test_each_session_resolves_to_its_own_user(client: TestClient) -> None:
    ada_id = register(client, email="ada@example.com").json()["id"]
    ada_token = client.cookies[SESSION_COOKIE]
    client.cookies.clear()
    grace_id = register(client, email="grace@example.com").json()["id"]
    grace_token = client.cookies[SESSION_COOKIE]

    client.cookies.set(SESSION_COOKIE, ada_token)
    assert client.get("/api/v1/auth/me").json()["id"] == ada_id
    client.cookies.set(SESSION_COOKIE, grace_token)
    assert client.get("/api/v1/auth/me").json()["id"] == grace_id
