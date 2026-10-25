import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import EventType, RoundResult, RoundStatus, RoundType
from app.schemas.common import Name, PartialUpdate, Reason, Url

Notes = Annotated[str, StringConstraints(max_length=20_000)]


class RoundLink(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    url: Url


class RoundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    round_type: RoundType
    # Timezone required: "10:00" means nothing without knowing whose 10:00.
    scheduled_at: AwareDatetime | None = None
    confirmation_deadline: AwareDatetime | None = None
    status: RoundStatus | None = Field(
        default=None, description="Defaults to 'upcoming' if scheduled_at is given, else 'not_scheduled'."
    )
    result: RoundResult = RoundResult.UNKNOWN
    follow_up_date: date | None = None
    completed_at: AwareDatetime | None = None
    links: list[RoundLink] = Field(default_factory=list, max_length=20)
    notes: Notes | None = None


class RoundUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"name", "round_type", "status", "result", "links", "position"})

    name: Name | None = None
    round_type: RoundType | None = None
    scheduled_at: AwareDatetime | None = None
    confirmation_deadline: AwareDatetime | None = None
    status: RoundStatus | None = None
    result: RoundResult | None = None
    follow_up_date: date | None = None
    completed_at: AwareDatetime | None = None
    links: list[RoundLink] | None = Field(default=None, max_length=20)
    notes: Notes | None = None
    position: int | None = Field(default=None, ge=0)
    change_reason: Reason | None = Field(
        default=None, description="Optional. Stored with any history entries this change creates."
    )


class RoundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    position: int
    name: str
    round_type: RoundType
    scheduled_at: datetime | None
    confirmation_deadline: datetime | None
    status: RoundStatus
    result: RoundResult
    follow_up_date: date | None
    completed_at: datetime | None
    links: list[RoundLink]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    round_id: uuid.UUID | None
    event_type: EventType
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    reason: str | None
    occurred_at: datetime
