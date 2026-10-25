import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.learning import (
    AttemptOutcome,
    EvidenceBasis,
    GapStatus,
    GapType,
    Level,
    TaskKind,
    TaskStatus,
)
from app.schemas.common import PartialUpdate

SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=20_000)]
Priority = Annotated[int, Field(ge=1, le=5, description="1 = highest.")]
Minutes = Annotated[int, Field(ge=0, le=1440)]


# --- gaps ----------------------------------------------------------------------------


class GapEvidenceRead(BaseModel):
    id: uuid.UUID
    basis: EvidenceBasis
    note: str | None
    created_at: datetime
    requirement_id: uuid.UUID | None
    requirement_text: str | None
    application_id: uuid.UUID | None
    company_name: str | None
    position_title: str | None
    question_id: uuid.UUID | None
    question_text: str | None
    journal_id: uuid.UUID | None


class ReassessmentRead(BaseModel):
    id: uuid.UUID
    assessed_at: datetime
    previous_status: GapStatus
    new_status: GapStatus
    confidence: Level
    summary: str
    task_attempt_id: uuid.UUID | None
    question_attempt_id: uuid.UUID | None
    cited: str | None  # a readable description of the cited attempt


class TaskAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempted_at: datetime
    duration_minutes: int | None
    outcome: AttemptOutcome
    notes: str | None


class TaskRead(BaseModel):
    id: uuid.UUID
    kind: TaskKind
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    due_date: date | None
    why: str | None
    skill_gap_id: uuid.UUID | None
    skill_name: str | None
    job_requirement_id: uuid.UUID | None
    requirement_text: str | None
    application_id: uuid.UUID | None
    application_label: str | None
    recruitment_round_id: uuid.UUID | None
    round_name: str | None
    question_id: uuid.UUID | None
    question_text: str | None
    created_at: datetime
    attempts: list[TaskAttemptRead]


class GapSummary(BaseModel):
    id: uuid.UUID
    skill_name: str
    gap_type: GapType
    importance: Level
    confidence: Level
    status: GapStatus
    priority: int
    target_date: date | None
    recommended_action: str | None
    created_at: datetime
    updated_at: datetime
    evidence_count: int
    application_count: int  # distinct applications the evidence comes from
    evidence_by_basis: dict[str, int]
    task_count: int
    completed_task_count: int


class GapDetail(GapSummary):
    notes: str | None
    evidence: list[GapEvidenceRead]
    reassessments: list[ReassessmentRead]
    tasks: list[TaskRead]


class GapCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: SkillName
    gap_type: GapType = GapType.UNCLASSIFIED
    importance: Level = Level.MEDIUM
    priority: Priority = 3
    target_date: date | None = None
    recommended_action: LongText | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = Field(
        description="Why you think this is a gap. Stored as evidence you provided."
    )


class GapFromSource(BaseModel):
    """Create a gap from a requirement or question, or attach the evidence to an existing gap."""

    model_config = ConfigDict(extra="forbid")

    skill_name: SkillName | None = Field(default=None, description="Defaults to the requirement's skill or the question's topic.")


class GapUpdate(PartialUpdate):
    """Status isn't editable here: change it through a reassessment, so the history is kept."""

    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"skill_name", "gap_type", "importance", "confidence", "priority"})

    skill_name: SkillName | None = None
    gap_type: GapType | None = None
    importance: Level | None = None
    confidence: Level | None = None
    priority: Priority | None = None
    target_date: date | None = None
    recommended_action: LongText | None = None
    notes: LongText | None = None


class ReassessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: GapStatus
    confidence: Level
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    task_attempt_id: uuid.UUID | None = None
    question_attempt_id: uuid.UUID | None = None


# --- tasks ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TaskKind = TaskKind.LEARNING
    title: Title
    description: LongText | None = None
    priority: Priority = 3
    due_date: date | None = None
    why: LongText | None = None
    skill_gap_id: uuid.UUID | None = None
    job_requirement_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    recruitment_round_id: uuid.UUID | None = None
    question_id: uuid.UUID | None = None


class TaskUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"title", "status", "priority"})

    title: Title | None = None
    description: LongText | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    why: LongText | None = None


class TaskAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_minutes: Minutes | None = None
    outcome: AttemptOutcome
    notes: LongText | None = None
