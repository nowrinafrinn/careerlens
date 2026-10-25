"""Accounts, passwords and sign-in sessions.

Route handlers call these functions; they never touch password hashes or
session tokens themselves.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import User, UserSession

_passwords = PasswordHash.recommended()  # Argon2id with library-recommended parameters

# Verified against when the email doesn't exist, so a failed login takes the
# same time either way and doesn't reveal which emails have accounts.
_DUMMY_HASH = _passwords.hash("careerlens-timing-equaliser")

def _invalid_credentials() -> AppError:
    # Same error for "no such email" and "wrong password".
    return AppError(401, "invalid_credentials", "The email or password is incorrect.")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register_user(db: Session, email: str, password: str, display_name: str | None) -> User:
    if not get_settings().allow_registration:
        raise AppError(403, "registration_closed", "New accounts can't be created on this server.")

    email = normalize_email(email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError(409, "email_taken", "An account with this email already exists.")

    user = User(email=email, password_hash=_passwords.hash(password), display_name=display_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two simultaneous sign-ups with the same email: the unique constraint wins.
        db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists.") from None
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        _passwords.verify(password, _DUMMY_HASH)
        raise _invalid_credentials()
    if not _passwords.verify(password, user.password_hash):
        raise _invalid_credentials()
    return user


def start_session(db: Session, user: User) -> str:
    """Creates a session and returns the raw token for the cookie.

    The raw token exists only in the cookie; the database keeps its hash.
    """
    now = datetime.now(UTC)
    # Housekeeping: drop this user's expired sessions while we're here.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= now))

    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=now + timedelta(days=get_settings().session_ttl_days),
        )
    )
    db.commit()
    return token


def user_for_token(db: Session, token: str) -> User | None:
    """Returns the signed-in user, or None if the token is unknown, revoked or expired."""
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == _hash_token(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    return session.user if session else None


def end_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))
    db.commit()
