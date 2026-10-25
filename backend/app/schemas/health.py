from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    # Current Alembic revision; None means migrations have never been applied.
    migration_revision: str | None
