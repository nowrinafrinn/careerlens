import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import ApplicationStatus
from app.schemas.common import Name, PartialUpdate, Reason, Url
from app.schemas.rounds import RoundRead

JobDescription = Annotated[str, StringConstraints(max_length=100_000)]
Source = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Notes = Annotated[str, StringConstraints(max_length=20_000)]


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: Name
    position_title: Name
    job_description: JobDescription | None = None
    job_url: Url | None = None
    source: Source | None = None
    deadline: date | None = None
    applied_on: date | None = Field(default=None, description="Set to today automatically when status is 'applied'.")
    status: ApplicationStatus = ApplicationStatus.INTERESTED
    notes: Notes | None = None


class ApplicationUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"company_name", "position_title", "status"})

    company_name: Name | None = None
    position_title: Name | None = None
    job_description: JobDescription | None = None
    job_url: Url | None = None
    source: Source | None = None
    deadline: date | None = None
    applied_on: date | None = None
    status: ApplicationStatus | None = None
    notes: Notes | None = None
    change_reason: Reason | None = Field(
        default=None, description="Optional. Stored with any history entries this change creates."
    )


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    position_title: str
    job_url: str | None
    source: str | None
    deadline: date | None
    applied_on: date | None
    status: ApplicationStatus
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationRead):
    """Everything about one application. The list view leaves out the long text fields."""

    job_description: str | None
    notes: str | None
    rounds: list[RoundRead]
