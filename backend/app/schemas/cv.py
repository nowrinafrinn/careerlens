import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.analysis.cv_parser import ParseStatus, SectionType
from app.schemas.common import PartialUpdate


class PassageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    position: int
    char_start: int
    char_end: int


class SectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_type: SectionType
    heading_text: str | None
    position: int
    user_corrected: bool
    passages: list[PassageRead]


class CVVersionRef(BaseModel):
    """The short form used inside an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    label: str
    parse_status: ParseStatus


class CVVersionSummary(CVVersionRef):
    is_confirmed: bool
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    application_count: int = 0


class CVVersionDetail(CVVersionSummary):
    parse_warnings: list[str]
    raw_text: str
    sections: list[SectionRead]


class CVVersionUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"label", "is_confirmed"})

    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    is_confirmed: bool | None = None


class SectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_type: SectionType
