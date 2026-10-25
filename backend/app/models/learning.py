import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.analysis import JobRequirement
from app.models.application import JobApplication, RecruitmentRound
from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import db_enum
from app.models.journal import Journal, Question, QuestionAttempt


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GapType(StrEnum):
    """The candidate's own diagnosis. Never inferred from a wrong answer."""

    UNCLASSIFIED = "unclassified"
    KNOWLEDGE = "knowledge"  # the concept isn't understood yet
    APPLICATION = "application"  # understood, but hard to apply
    SPEED = "speed"  # solvable, but too slowly
    RECALL = "recall"  # known, but hard to retrieve under pressure
    PREPARATION = "preparation"  # needs structured practice
    COMMUNICATION = "communication"  # hard to explain clearly


class Level(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GapStatus(StrEnum):
    OPEN = "open"
    IMPROVING = "improving"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EvidenceBasis(StrEnum):
    """Where a piece of evidence comes from, so facts and guesses never mix."""

    USER_CONFIRMED = "user_confirmed"  # the candidate said so
    RECORDED_OUTCOME = "recorded_outcome"  # from a question/attempt record
    INTERVIEWER_FEEDBACK = "interviewer_feedback"
    USER_INTERPRETATION = "user_interpretation"
    HYPOTHESIS = "hypothesis"  # an inference, not confirmed


class TaskKind(StrEnum):
    LEARNING = "learning"
    PREPARATION = "preparation"


class TaskStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_MORE_PRACTICE = "needs_more_practice"


class AttemptOutcome(StrEnum):
    STRUGGLED = "struggled"
    PARTIAL = "partial"
    SOLID = "solid"


class SkillGap(UUIDPrimaryKey, Timestamps, Base):
    """Something the candidate wants to learn or improve, backed by evidence. One per skill."""

    __tablename__ = "skill_gaps"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="priority_range"),
        # One gap per skill per user, regardless of capitalisation. text(), not func.lower("skill_name"):
        # the latter would lowercase the literal string 'skill_name' and allow one gap per user.
        Index("uq_skill_gaps_user_skill", "user_id", text("lower(skill_name)"), unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_name: Mapped[str] = mapped_column(String(100))
    gap_type: Mapped[GapType] = mapped_column(db_enum(GapType, "gap_type"), default=GapType.UNCLASSIFIED)
    importance: Mapped[Level] = mapped_column(db_enum(Level, "gap_importance"))
    confidence: Mapped[Level] = mapped_column(db_enum(Level, "gap_confidence"), default=Level.MEDIUM)
    status: Mapped[GapStatus] = mapped_column(db_enum(GapStatus, "gap_status"), default=GapStatus.OPEN)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)  # 1 = highest
    target_date: Mapped[date | None] = mapped_column(Date)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    evidence: Mapped[list["GapEvidence"]] = relationship(
        back_populates="gap", order_by="GapEvidence.created_at", cascade="all, delete-orphan", passive_deletes=True
    )
    reassessments: Mapped[list["GapReassessment"]] = relationship(
        back_populates="gap", order_by="GapReassessment.assessed_at", cascade="all, delete-orphan", passive_deletes=True
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="skill_gap", order_by="Task.created_at")


class GapEvidence(UUIDPrimaryKey, Base):
    """Why a gap exists: a requirement, a question, a journal or a note, and what kind of evidence it is."""

    __tablename__ = "gap_evidence"
    __table_args__ = (
        CheckConstraint(
            "requirement_id IS NOT NULL OR question_id IS NOT NULL OR journal_id IS NOT NULL OR note IS NOT NULL",
            name="has_source",
        ),
    )

    skill_gap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skill_gaps.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_requirements.id", ondelete="SET NULL"))
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"))
    journal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journals.id", ondelete="SET NULL"))
    basis: Mapped[EvidenceBasis] = mapped_column(db_enum(EvidenceBasis, "evidence_basis"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    gap: Mapped[SkillGap] = relationship(back_populates="evidence")
    requirement: Mapped[JobRequirement | None] = relationship()
    question: Mapped[Question | None] = relationship()
    journal: Mapped[Journal | None] = relationship()


class Task(UUIDPrimaryKey, Timestamps, Base):
    """A learning or preparation task, traceable to what motivated it."""

    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("priority BETWEEN 1 AND 5", name="priority_range"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[TaskKind] = mapped_column(db_enum(TaskKind, "task_kind"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(db_enum(TaskStatus, "task_status"), default=TaskStatus.PLANNED)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)
    due_date: Mapped[date | None] = mapped_column(Date)
    why: Mapped[str | None] = mapped_column(Text)  # what motivated it, in words
    skill_gap_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("skill_gaps.id", ondelete="SET NULL"), index=True)
    job_requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_requirements.id", ondelete="SET NULL"))
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"), index=True
    )
    recruitment_round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recruitment_rounds.id", ondelete="SET NULL"), index=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    skill_gap: Mapped[SkillGap | None] = relationship(back_populates="tasks")
    requirement: Mapped[JobRequirement | None] = relationship()
    application: Mapped[JobApplication | None] = relationship()
    round: Mapped[RecruitmentRound | None] = relationship()
    question: Mapped[Question | None] = relationship()
    attempts: Mapped[list["TaskAttempt"]] = relationship(
        back_populates="task", order_by="TaskAttempt.attempted_at", cascade="all, delete-orphan", passive_deletes=True
    )


class TaskAttempt(UUIDPrimaryKey, Base):
    __tablename__ = "task_attempts"
    __table_args__ = (CheckConstraint("duration_minutes IS NULL OR duration_minutes >= 0", name="duration_positive"),)

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[AttemptOutcome] = mapped_column(db_enum(AttemptOutcome, "attempt_outcome"))
    notes: Mapped[str | None] = mapped_column(Text)

    task: Mapped[Task] = relationship(back_populates="attempts")


class GapReassessment(UUIDPrimaryKey, Base):
    """Append-only: each change of a gap's status, with the evidence behind it."""

    __tablename__ = "gap_reassessments"

    skill_gap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skill_gaps.id", ondelete="CASCADE"), index=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    previous_status: Mapped[GapStatus] = mapped_column(db_enum(GapStatus, "previous_status"))
    new_status: Mapped[GapStatus] = mapped_column(db_enum(GapStatus, "new_status"))
    confidence: Mapped[Level] = mapped_column(db_enum(Level, "reassessment_confidence"))
    summary: Mapped[str] = mapped_column(Text)
    task_attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_attempts.id", ondelete="SET NULL"))
    question_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_attempts.id", ondelete="SET NULL")
    )

    gap: Mapped[SkillGap] = relationship(back_populates="reassessments")
    task_attempt: Mapped[TaskAttempt | None] = relationship()
    question_attempt: Mapped[QuestionAttempt | None] = relationship()
