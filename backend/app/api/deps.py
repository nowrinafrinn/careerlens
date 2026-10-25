"""Dependencies shared by route handlers."""

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import User
from app.services import auth as auth_service

SESSION_COOKIE = "careerlens_session"

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    user = auth_service.user_for_token(db, session_token) if session_token else None
    if user is None:
        raise AppError(401, "not_authenticated", "You need to sign in.")
    return user


# Every route that reads or writes a user's records takes `user: CurrentUser`
# and filters by `user.id`. That is how one user's data stays invisible to another.
CurrentUser = Annotated[User, Depends(get_current_user)]
