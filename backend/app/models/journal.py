import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.journal_templates import JournalTemplate
from app.models.application import JobApplication, RecruitmentRound
from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import db_enum


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"


class ResponseQuality(StrEnum):
    """How it went, in the candidate's own judgement."""

    CONFIDENT = "confident"
    PARTIAL = "partial"
    COULD_NOT_ANSWER = "could_not_answer"
    NOT_ATTEMPTED = "not_attempted"


class PracticeStatus(StrEnum):
    NEW = "new"
    TO_PRACTICE = "to_practice"
    PRACTICING = "practicing"
    COMFORTABLE = "comfortable"  # only ever set by the candidate


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Journal(UUIDPrimaryKey, Timestamps, Base):
    """What happened in a recruitment event, recorded through structured prompts."""

    __tablename__ = "journals"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recruitment_rounds.id", ondelete="SET NULL"), index=True
    )
    template: Mapped[JournalTemplate] = mapped_column(db_enum(JournalTemplate, "journal_template"))
    occurred_on: Mapped[date | None] = mapped_column(Date)
    responses: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)  # prompt key -> answer
    # Kept apart on purpose: what was actually said vs how the candidate reads it.
    interviewer_feedback: Mapped[str | None] = mapped_column(Text)
    user_interpretation: Mapped[str | None] = mapped_column(Text)
    follow_up_actions: Mapped[str | None] = mapped_column(Text)
    # Python-side so journals created in one transaction still have an order.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped[JobApplication] = relationship()
    round: Mapped[RecruitmentRound | None] = relationship()
    questions: Mapped[list["Question"]] = relationship(back_populates="journal", order_by="Question.created_at")


class Question(UUIDPrimaryKey, Timestamps, Base):
    """One question from a recruitment event, kept in the personal question bank."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 1 AND 5", name="confidence_range"),
        CheckConstraint("time_spent_minutes IS NULL OR time_spent_minutes >= 0", name="time_spent_positive"),
        Index("ix_questions_user_id_topic", "user_id", "topic"),
        # Trigram index (pg_trgm, enabled in migration 0001) keeps ILIKE search fast as the bank grows.
        Index("ix_questions_text_trgm", "text", postgresql_using="gin", postgresql_ops={"text": "gin_trgm_ops"}),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # SET NULL: the question stays in the bank even if its source goes away.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"), index=True
    )
    round_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recruitment_rounds.id", ondelete="SET NULL"))
    journal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journals.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(String(100))
    topic: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[Difficulty] = mapped_column(db_enum(Difficulty, "difficulty"), default=Difficulty.UNKNOWN)
    # Three different sources, three columns, never mixed:
    original_answer: Mapped[str | None] = mapped_column(Text)  # what the candidate said at the time; immutable
    verified_solution: Mapped[str | None] = mapped_column(Text)  # added later, checked by the candidate
    ai_suggestion: Mapped[str | None] = mapped_column(Text)  # a generated suggestion (not used yet)
    response_quality: Mapped[ResponseQuality] = mapped_column(db_enum(ResponseQuality, "response_quality"))
    time_spent_minutes: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    difficulty_reason: Mapped[str | None] = mapped_column(Text)
    practice_status: Mapped[PracticeStatus] = mapped_column(db_enum(PracticeStatus, "practice_status"))
    asked_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped[JobApplication | None] = relationship()
    round: Mapped[RecruitmentRound | None] = relationship()
    journal: Mapped[Journal | None] = relationship(back_populates="questions")
    attempts: Mapped[list["QuestionAttempt"]] = relationship(
        back_populates="question", order_by="QuestionAttempt.attempted_at", cascade="all, delete-orphan",
        passive_deletes=True,
    )


class QuestionAttempt(UUIDPrimaryKey, Base):
    """A later try at a question. The original answer is never overwritten."""

    __tablename__ = "question_attempts"
    __table_args__ = (
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 1 AND 5", name="confidence_range"),
        CheckConstraint("time_spent_minutes IS NULL OR time_spent_minutes >= 0", name="time_spent_positive"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    answer: Mapped[str | None] = mapped_column(Text)
    response_quality: Mapped[ResponseQuality] = mapped_column(db_enum(ResponseQuality, "response_quality"))
    time_spent_minutes: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)

    question: Mapped[Question] = relationship(back_populates="attempts")
