"""Recruitment rounds inside an application.

Rules this module enforces:
- A round's status (where it is in time) and result (how it went) are
  independent: completing a round never sets it to passed.
- Nothing here changes the application's own status.
- Changing a date never loses the old one: it is written to the history.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import JobApplication, RecruitmentRound, User
from app.models.enums import EventType, RoundStatus
from app.services.applications import get_application
from app.services.events import record_event

_OTHER_DATE_FIELDS = ("confirmation_deadline", "follow_up_date")


def _not_found() -> AppError:
    return AppError(404, "not_found", "Round not found.")


def get_round(db: Session, user: User, round_id: uuid.UUID) -> RecruitmentRound:
    # Reached only through an application the user owns.
    rnd = db.scalar(
        select(RecruitmentRound)
        .join(JobApplication, RecruitmentRound.application_id == JobApplication.id)
        .where(RecruitmentRound.id == round_id, JobApplication.user_id == user.id)
    )
    if rnd is None:
        raise _not_found()
    return rnd


def list_rounds(db: Session, user: User, application_id: uuid.UUID) -> list[RecruitmentRound]:
    return list(get_application(db, user, application_id).rounds)


def create_round(db: Session, user: User, application_id: uuid.UUID, data: dict[str, Any]) -> RecruitmentRound:
    application = get_application(db, user, application_id)

    if data.get("status") is None:
        data = {**data, "status": RoundStatus.UPCOMING if data.get("scheduled_at") else RoundStatus.NOT_SCHEDULED}
    if data["status"] == RoundStatus.COMPLETED and data.get("completed_at") is None:
        data = {**data, "completed_at": datetime.now(UTC)}

    position = max((r.position for r in application.rounds), default=-1) + 1
    rnd = RecruitmentRound(position=position, **data)
    application.rounds.append(rnd)
    db.flush()

    record_event(
        db,
        user_id=user.id,
        application_id=application.id,
        round_id=rnd.id,
        event_type=EventType.ROUND_CREATED,
        new={
            "round_name": rnd.name,
            "round_type": rnd.round_type,
            "scheduled_at": rnd.scheduled_at,
            "status": rnd.status,
        },
    )
    db.commit()
    return rnd


def update_round(
    db: Session, user: User, round_id: uuid.UUID, changes: dict[str, Any], reason: str | None = None
) -> RecruitmentRound:
    rnd = get_round(db, user, round_id)
    before = {field: getattr(rnd, field) for field in ("scheduled_at", "status", "result", *_OTHER_DATE_FIELDS)}

    # Convenience defaults; an explicit value in the request always wins.
    if changes.get("scheduled_at") and rnd.status == RoundStatus.NOT_SCHEDULED and "status" not in changes:
        changes = {**changes, "status": RoundStatus.UPCOMING}
    if (
        changes.get("status") == RoundStatus.COMPLETED
        and rnd.completed_at is None
        and "completed_at" not in changes
    ):
        changes = {**changes, "completed_at": datetime.now(UTC)}

    for field, value in changes.items():
        setattr(rnd, field, value)

    def event(event_type: EventType, old: dict[str, Any], new: dict[str, Any]) -> None:
        record_event(
            db,
            user_id=user.id,
            application_id=rnd.application_id,
            round_id=rnd.id,
            event_type=event_type,
            old={"round_name": rnd.name, **old},
            new={"round_name": rnd.name, **new},
            reason=reason,
        )

    if rnd.scheduled_at != before["scheduled_at"]:
        event_type = EventType.ROUND_SCHEDULED if before["scheduled_at"] is None else EventType.ROUND_RESCHEDULED
        event(event_type, {"scheduled_at": before["scheduled_at"]}, {"scheduled_at": rnd.scheduled_at})

    old_dates = {f: before[f] for f in _OTHER_DATE_FIELDS if getattr(rnd, f) != before[f]}
    if old_dates:
        event(EventType.ROUND_DATE_CHANGED, old_dates, {f: getattr(rnd, f) for f in old_dates})

    if rnd.status != before["status"]:
        event(EventType.ROUND_STATUS_CHANGED, {"status": before["status"]}, {"status": rnd.status})

    if rnd.result != before["result"]:
        event(EventType.ROUND_RESULT_RECORDED, {"result": before["result"]}, {"result": rnd.result})

    db.commit()
    return rnd


def delete_round(db: Session, user: User, round_id: uuid.UUID, reason: str | None = None) -> None:
    """Removes a round (e.g. created by mistake). Its history stays, plus a snapshot."""
    rnd = get_round(db, user, round_id)
    record_event(
        db,
        user_id=user.id,
        application_id=rnd.application_id,
        round_id=rnd.id,  # set to NULL by the database when the round row goes
        event_type=EventType.ROUND_DELETED,
        old={
            "round_name": rnd.name,
            "round_type": rnd.round_type,
            "scheduled_at": rnd.scheduled_at,
            "status": rnd.status,
            "result": rnd.result,
        },
        reason=reason,
    )
    db.flush()
    rnd.application.rounds.remove(rnd)  # delete-orphan cascade removes the row
    db.commit()
