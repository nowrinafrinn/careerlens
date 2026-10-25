import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import JobApplication, RecruitmentEvent, RecruitmentRound
from app.models.enums import ApplicationStatus
from app.schemas.applications import ApplicationCreate, ApplicationDetail, ApplicationRead, ApplicationUpdate
from app.schemas.common import Page
from app.schemas.rounds import EventRead, RoundCreate, RoundRead
from app.services import applications as service
from app.services import rounds as rounds_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=Page[ApplicationRead])
def list_applications(
    user: CurrentUser,
    db: DbSession,
    status_: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Matches company or position.")] = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ApplicationRead]:
    items, total = service.list_applications(
        db, user, status=status_, q=q, include_archived=include_archived, limit=limit, offset=offset
    )
    return Page[ApplicationRead](
        items=[ApplicationRead.model_validate(a) for a in items], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, user: CurrentUser, db: DbSession) -> JobApplication:
    return service.create_application(db, user, body.model_dump())


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobApplication:
    return service.get_application(db, user, application_id)


@router.patch("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: uuid.UUID, body: ApplicationUpdate, user: CurrentUser, db: DbSession
) -> JobApplication:
    return service.update_application(
        db, user, application_id, body.changes(exclude={"change_reason"}), reason=body.change_reason
    )


@router.post("/{application_id}/archive", response_model=ApplicationDetail)
def archive_application(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobApplication:
    return service.set_archived(db, user, application_id, archived=True)


@router.post("/{application_id}/restore", response_model=ApplicationDetail)
def restore_application(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobApplication:
    return service.set_archived(db, user, application_id, archived=False)


@router.get("/{application_id}/timeline", response_model=list[EventRead])
def application_timeline(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[RecruitmentEvent]:
    """Every recorded change for this application and its rounds, oldest first."""
    return service.timeline(db, user, application_id)


@router.get("/{application_id}/rounds", response_model=list[RoundRead])
def list_rounds(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[RecruitmentRound]:
    return rounds_service.list_rounds(db, user, application_id)


@router.post("/{application_id}/rounds", response_model=RoundRead, status_code=status.HTTP_201_CREATED)
def create_round(application_id: uuid.UUID, body: RoundCreate, user: CurrentUser, db: DbSession) -> RecruitmentRound:
    return rounds_service.create_round(db, user, application_id, body.model_dump())
