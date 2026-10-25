"""The recruitment history. Only ever inserts."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy.orm import Session

from app.models import RecruitmentEvent
from app.models.enums import EventType


def _to_json(values: dict[str, Any] | None) -> dict[str, Any] | None:
    """Dates and enums become plain JSON values. Date-times are stored in UTC,
    so an old value read from the database and a new value from a request in
    +06:00 look the same and compare correctly."""
    if values is None:
        return None
    normalized = {k: v.astimezone(UTC) if isinstance(v, datetime) else v for k, v in values.items()}
    return to_jsonable_python(normalized)


def record_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    application_id: uuid.UUID,
    event_type: EventType,
    round_id: uuid.UUID | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    reason: str | None = None,
) -> RecruitmentEvent:
    event = RecruitmentEvent(
        user_id=user_id,
        application_id=application_id,
        round_id=round_id,
        event_type=event_type,
        old_value=_to_json(old),
        new_value=_to_json(new),
        reason=reason,
    )
    db.add(event)
    return event
