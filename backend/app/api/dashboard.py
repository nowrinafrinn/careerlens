from dataclasses import asdict
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import DashboardRead, InsightsRead
from app.services import dashboard as dashboard_service
from app.services import insights as insights_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(user: CurrentUser, db: DbSession, today: date | None = None) -> dict:
    """What needs attention, what's coming in the next 14 days, what's waiting on a result,
    and where your learning stands. Pass `today` as your local date so date-based items match
    your calendar (defaults to the server's date in UTC)."""
    return asdict(dashboard_service.build(db, user, dashboard_service.parse_today(today)))


@router.get("/insights", response_model=InsightsRead)
def insights(user: CurrentUser, db: DbSession) -> dict:
    """Patterns across your records. Each insight lists its sources and how many observations
    it rests on; below the minimum it is marked as not enough data, not presented as a pattern."""
    return insights_service.build(db, user)
