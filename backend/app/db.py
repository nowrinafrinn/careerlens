"""Database engine and the per-request session dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()
if settings.db_serverless:
    # Serverless: no pool of our own (the external pooler, e.g. Supabase's, does
    # that), and no prepared statements, which transaction-mode poolers break.
    engine = create_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"connect_timeout": settings.db_connect_timeout, "prepare_threshold": None},
    )
else:
    # pool_pre_ping checks a pooled connection is alive before use, so a restarted
    # Postgres container doesn't cause one failed request per stale connection.
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Services decide when to commit; nothing is committed implicitly.
    """
    with SessionLocal() as session:
        yield session
