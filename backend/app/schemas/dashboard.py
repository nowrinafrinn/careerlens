import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.journal_templates import JournalTemplate
from app.models.enums import RoundType
from app.models.journal import PracticeStatus
from app.models.learning import GapStatus, TaskKind, TaskStatus


class AppRef(BaseModel):
    application_id: uuid.UUID
    company_name: str
    position_title: str


class AttentionItem(BaseModel):
    kind: Literal["deadline_passed", "round_passed", "confirmation_passed", "task_overdue"]
    date: date
    message: str
    application_id: uuid.UUID | None = None
    company_name: str | None = None
    position_title: str | None = None
    round_id: uuid.UUID | None = None
    round_name: str | None = None
    round_type: RoundType | None = None
    task_id: uuid.UUID | None = None
    title: str | None = None


class UpcomingRound(AppRef):
    round_id: uuid.UUID
    round_name: str
    round_type: RoundType
    scheduled_at: datetime
    prep_total: int
    prep_done: int


class UpcomingDeadline(AppRef):
    date: date


class PendingResult(AppRef):
    round_id: uuid.UUID
    round_name: str
    round_type: RoundType
    since: date


class FollowUp(AppRef):
    round_id: uuid.UUID
    round_name: str
    round_type: RoundType
    date: date
    overdue: bool


class TaskItem(BaseModel):
    task_id: uuid.UUID
    title: str
    kind: TaskKind
    status: TaskStatus
    priority: int
    due_date: date | None
    skill_gap_id: uuid.UUID | None
    application_id: uuid.UUID | None
    round_id: uuid.UUID | None


class ReassessmentItem(BaseModel):
    skill_gap_id: uuid.UUID
    skill_name: str
    previous_status: GapStatus
    new_status: GapStatus
    assessed_at: datetime
    summary: str


class PracticeItem(BaseModel):
    question_id: uuid.UUID
    text: str
    topic: str | None
    practice_status: PracticeStatus


class JournalItem(AppRef):
    journal_id: uuid.UUID
    template: JournalTemplate
    round_name: str | None
    created_at: datetime
    question_count: int


class AnalysisItem(AppRef):
    analysis_id: uuid.UUID
    created_at: datetime
    coverage_percent: int | None
    required_total: int
    demonstrated: int
    needs_your_input: int  # required lines not fully shown that you haven't assessed yet
    is_stale: bool


class DashboardRead(BaseModel):
    today: date
    application_counts: dict[str, int]
    needs_attention: list[AttentionItem]
    upcoming_rounds: list[UpcomingRound]
    upcoming_deadlines: list[UpcomingDeadline]
    pending_results: list[PendingResult]
    follow_ups: list[FollowUp]
    top_tasks: list[TaskItem]
    gap_counts: dict[str, int]
    recent_reassessments: list[ReassessmentItem]
    questions_to_practice: list[PracticeItem]
    questions_to_practice_total: int
    recent_journals: list[JournalItem]
    analyses: list[AnalysisItem]


# --- insights ------------------------------------------------------------------------


class InsightSource(BaseModel):
    kind: Literal["application", "question", "skill_gap", "requirement", "reassessment"]
    id: uuid.UUID
    label: str
    application_id: uuid.UUID | None = None  # for links to a requirement's analysis


class InsightRead(BaseModel):
    key: str
    category: Literal[
        "recurring_skill", "cv_evidence", "difficulty_topic", "recurring_question_topic", "shared_priority",
        "improvement", "preparation_before_improvement",
    ]
    title: str
    statement: str
    observation_count: int
    sufficient_data: bool  # False below the minimum number of observations: not a pattern yet
    basis: Literal["job_descriptions", "cv_analysis", "recorded_outcomes", "your_statements", "mixed"]
    caveat: str
    sources: list[InsightSource]


class InsightsRead(BaseModel):
    minimum_observations: int
    insights: list[InsightRead]
    data_notes: list[str]  # what more data would make insights possible
