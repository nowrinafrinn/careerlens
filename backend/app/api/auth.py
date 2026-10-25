from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import SESSION_COOKIE, CurrentUser, DbSession
from app.config import get_settings
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,  # page JavaScript can't read it, so an XSS bug can't steal it
        samesite="lax",  # not sent on cross-site POSTs: the CSRF defence for this MVP
        secure=settings.cookie_secure,
        path="/",
    )


def _sign_in(db: DbSession, response: Response, user: User, old_token: str | None) -> None:
    if old_token:
        auth_service.end_session(db, old_token)
    _set_session_cookie(response, auth_service.start_session(db, user))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    db: DbSession,
    response: Response,
    old_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """Creates an account and signs it in."""
    user = auth_service.register_user(db, body.email, body.password, body.display_name)
    _sign_in(db, response, user, old_token)
    return user


@router.post("/login", response_model=UserRead)
def login(
    body: LoginRequest,
    db: DbSession,
    response: Response,
    old_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    user = auth_service.authenticate(db, body.email, body.password)
    _sign_in(db, response, user, old_token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    response: Response,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    """Ends the session on the server, not just in this browser. Safe to call when signed out."""
    if token:
        auth_service.end_session(db, token)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=get_settings().cookie_secure)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
