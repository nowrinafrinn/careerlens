import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.journal_templates import JournalTemplate
from app.models.enums import RoundType
from app.models.journal import Difficulty, PracticeStatus, ResponseQuality
from app.schemas.common import PartialUpdate

LongText = Annotated[str, StringConstraints(max_length=20_000)]
ShortLabel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)]
Minutes = Annotated[int, Field(ge=0, le=1440)]
Confidence = Annotated[int, Field(ge=1, le=5, description="1 = not at all confident, 5 = very confident.")]


# --- templates ---------------------------------------------------------------------------


class PromptRead(BaseModel):
    key: str
    question: str
    hint: str


class TemplateRead(BaseModel):
    template: JournalTemplate
    label: str
    description: str
    prompts: list[PromptRead]


# --- questions -------------------------------------------------------------------------------


class QuestionFields(BaseModel):
    """What can be recorded about a question when it's first saved."""

    model_config = ConfigDict(extra="forbid")

    text: QuestionText
    subject: ShortLabel | None = None
    topic: ShortLabel | None = None
    difficulty: Difficulty = Difficulty.UNKNOWN
    original_answer: LongText | None = Field(default=None, description="What you answered at the time. Can't be changed later.")
    response_quality: ResponseQuality
    time_spent_minutes: Minutes | None = None
    confidence: Confidence | None = None
    difficulty_reason: LongText | None = None
    asked_on: date | None = None
    practice_status: PracticeStatus | None = Field(
        default=None, description="Defaults to 'to_practice' for partial or unanswered questions, else 'new'."
    )


class QuestionCreate(QuestionFields):
    """A question recorded on its own, optionally linked to an application and round."""

    application_id: uuid.UUID | None = None
    round_id: uuid.UUID | None = None


class QuestionUpdate(PartialUpdate):
    """Later edits. The original answer, how it went, time and confidence describe the
    event itself and can't be changed; record a new attempt instead."""

    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"text", "difficulty", "practice_status"})

    text: QuestionText | None = None
    subject: ShortLabel | None = None
    topic: ShortLabel | None = None
    difficulty: Difficulty | None = None
    difficulty_reason: LongText | None = None
    verified_solution: LongText | None = None
    practice_status: PracticeStatus | None = None
    asked_on: date | None = None


class AttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: LongText | None = None
    response_quality: ResponseQuality
    time_spent_minutes: Minutes | None = None
    confidence: Confidence | None = None
    notes: LongText | None = None


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempted_at: datetime
    answer: str | None
    response_quality: ResponseQuality
    time_spent_minutes: int | None
    confidence: int | None
    notes: str | None


class QuestionRead(BaseModel):
    id: uuid.UUID
    text: str
    subject: str | None
    topic: str | None
    difficulty: Difficulty
    original_answer: str | None
    verified_solution: str | None
    ai_suggestion: str | None
    response_quality: ResponseQuality
    time_spent_minutes: int | None
    confidence: int | None
    difficulty_reason: str | None
    practice_status: PracticeStatus
    asked_on: date | None
    created_at: datetime
    application_id: uuid.UUID | None
    company_name: str | None
    position_title: str | None
    round_id: uuid.UUID | None
    round_name: str | None
    round_type: RoundType | None
    journal_id: uuid.UUID | None
    attempt_count: int
    latest_attempt: AttemptRead | None


class QuestionDetail(QuestionRead):
    attempts: list[AttemptRead]
    skill_gap_id: uuid.UUID | None = None  # the learning-plan gap this question is evidence for, if any


class QuestionFacets(BaseModel):
    """Values that exist in your bank, for filter menus."""

    companies: list[str]
    positions: list[str]
    topics: list[str]
    subjects: list[str]


# --- journals --------------------------------------------------------------------------------


class JournalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: uuid.UUID
    round_id: uuid.UUID | None = None
    template: JournalTemplate
    occurred_on: date | None = None
    responses: dict[str, LongText] = Field(default_factory=dict, description="Prompt key → your answer.")
    interviewer_feedback: LongText | None = Field(default=None, description="Only what was explicitly said to you.")
    user_interpretation: LongText | None = Field(default=None, description="Your own reading of how it went.")
    follow_up_actions: LongText | None = None
    questions: list[QuestionFields] = Field(default_factory=list, max_length=50)


class JournalUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"responses"})

    round_id: uuid.UUID | None = None
    occurred_on: date | None = None
    responses: dict[str, LongText] | None = None
    interviewer_feedback: LongText | None = None
    user_interpretation: LongText | None = None
    follow_up_actions: LongText | None = None


class JournalRead(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    company_name: str
    position_title: str
    round_id: uuid.UUID | None
    round_name: str | None
    template: JournalTemplate
    occurred_on: date | None
    responses: dict[str, str]
    interviewer_feedback: str | None
    user_interpretation: str | None
    follow_up_actions: str | None
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionRead]
