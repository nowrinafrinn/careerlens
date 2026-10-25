"""Job applications: create, read, update, archive, history.

Every function takes the signed-in user and only ever sees that user's rows.
Another user's application is reported as "not found", never "forbidden",
so the API doesn't confirm that it exists.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import CVVersion, JobApplication, RecruitmentEvent, User
from app.models.enums import ApplicationStatus, EventType
from app.services import cvs
from app.services.events import record_event

# Changes to these fields are written to the history.
_DATE_FIELDS = ("deadline", "applied_on")


def _not_found() -> AppError:
    return AppError(404, "not_found", "Application not found.")


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_application(db: Session, user: User, application_id: uuid.UUID) -> JobApplication:
    application = db.scalar(
        select(JobApplication).where(JobApplication.id == application_id, JobApplication.user_id == user.id)
    )
    if application is None:
        raise _not_found()
    return application


def list_applications(
    db: Session,
    user: User,
    *,
    status: ApplicationStatus | None = None,
    q: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[JobApplication], int]:
    query = select(JobApplication).where(JobApplication.user_id == user.id)
    if not include_archived:
        query = query.where(JobApplication.archived_at.is_(None))
    if status is not None:
        query = query.where(JobApplication.status == status)
    if q:
        pattern = f"%{_escape_like(q.strip())}%"
        query = query.where(
            or_(
                JobApplication.company_name.ilike(pattern, escape="\\"),
                JobApplication.position_title.ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(JobApplication.updated_at.desc(), JobApplication.created_at.desc(), JobApplication.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def create_application(db: Session, user: User, data: dict[str, Any]) -> JobApplication:
    cvs.ensure_owned(db, user, data.get("cv_version_id"))
    application = JobApplication(user_id=user.id, **data)
    if application.status == ApplicationStatus.APPLIED and application.applied_on is None:
        application.applied_on = date.today()
    db.add(application)
    db.flush()  # assigns defaults and makes the row exist before the event references it

    record_event(
        db,
        user_id=user.id,
        application_id=application.id,
        event_type=EventType.APPLICATION_CREATED,
        new={
            "company_name": application.company_name,
            "position_title": application.position_title,
            "status": application.status,
            "cv_version_id": application.cv_version_id,
        },
    )
    db.commit()
    return application


def update_application(
    db: Session, user: User, application_id: uuid.UUID, changes: dict[str, Any], reason: str | None = None
) -> JobApplication:
    """Applies a partial update. Status and date changes are added to the history."""
    application = get_application(db, user, application_id)

    new_status = changes.get("status")
    if (
        new_status == ApplicationStatus.APPLIED
        and application.status != ApplicationStatus.APPLIED
        and application.applied_on is None
        and "applied_on" not in changes
    ):
        changes = {**changes, "applied_on": date.today()}

    if "cv_version_id" in changes:
        cvs.ensure_owned(db, user, changes["cv_version_id"])

    old_dates: dict[str, Any] = {}
    new_dates: dict[str, Any] = {}
    old_status = application.status
    old_cv = application.cv_version

    for field, value in changes.items():
        if getattr(application, field) == value:
            continue
        if field in _DATE_FIELDS:
            old_dates[field] = getattr(application, field)
            new_dates[field] = value
        setattr(application, field, value)

    if application.status != old_status:
        record_event(
            db,
            user_id=user.id,
            application_id=application.id,
            event_type=EventType.APPLICATION_STATUS_CHANGED,
            old={"status": old_status},
            new={"status": application.status},
            reason=reason,
        )
    if new_dates:
        record_event(
            db,
            user_id=user.id,
            application_id=application.id,
            event_type=EventType.APPLICATION_DATE_CHANGED,
            old=old_dates,
            new=new_dates,
            reason=reason,
        )
    if application.cv_version_id != (old_cv.id if old_cv else None):
        db.flush()
        db.refresh(application, ["cv_version"])
        new_cv = application.cv_version

        def describe(cv: CVVersion | None) -> dict[str, Any]:
            # The label is copied in, so the history still reads well if the CV is renamed or deleted.
            return {"cv_version_id": cv.id if cv else None, "cv_label": cv.label if cv else None}

        record_event(
            db,
            user_id=user.id,
            application_id=application.id,
            event_type=EventType.APPLICATION_CV_CHANGED,
            old=describe(old_cv),
            new=describe(new_cv),
            reason=reason,
        )
    db.commit()
    return application


def set_archived(db: Session, user: User, application_id: uuid.UUID, archived: bool) -> JobApplication:
    application = get_application(db, user, application_id)
    if (application.archived_at is not None) == archived:
        return application  # already in the requested state: nothing to record

    application.archived_at = datetime.now(UTC) if archived else None
    record_event(
        db,
        user_id=user.id,
        application_id=application.id,
        event_type=EventType.APPLICATION_ARCHIVED if archived else EventType.APPLICATION_RESTORED,
    )
    db.commit()
    return application


def timeline(db: Session, user: User, application_id: uuid.UUID) -> list[RecruitmentEvent]:
    get_application(db, user, application_id)  # ownership check
    return list(
        db.scalars(
            select(RecruitmentEvent)
            .where(RecruitmentEvent.application_id == application_id)
            .order_by(RecruitmentEvent.occurred_at, RecruitmentEvent.id)
        ).all()
    )
