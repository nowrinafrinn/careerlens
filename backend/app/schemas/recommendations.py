import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.analysis.recommendations import ChangeType, Kind
from app.models.analysis import Origin, RecommendationStatus


class RecommendationRead(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_text: str
    cv_passage_id: uuid.UUID | None
    kind: Kind
    change_type: ChangeType
    title: str
    rationale: str
    original_text: str | None
    suggested_text: str | None
    assumptions: list[str]
    terms: list[str]
    origin: Origin
    status: RecommendationStatus
    final_text: str | None
    decided_at: datetime | None
    # Numbers in the text you'd use that weren't in your original wording. Check them.
    number_warnings: list[str]


class RecommendationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["proposed", "accepted", "edited", "rejected"]
    final_text: Annotated[str, StringConstraints(max_length=2000)] | None = None
