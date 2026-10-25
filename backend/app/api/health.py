from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    """Reports whether the API can reach the database and which migration it is on."""
    try:
        db.execute(text("SELECT 1"))
        # to_regclass returns NULL instead of erroring when the table doesn't exist yet.
        has_version_table = db.execute(text("SELECT to_regclass('alembic_version') IS NOT NULL")).scalar_one()
        revision = (
            db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if has_version_table
            else None
        )
    except SQLAlchemyError:
        response.status_code = 503
        return HealthResponse(status="degraded", database="unavailable", migration_revision=None)

    return HealthResponse(status="ok", database="ok", migration_revision=revision)
