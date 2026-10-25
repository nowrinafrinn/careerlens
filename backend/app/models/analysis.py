import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.analysis.evidence import EvidenceStatus, Relevance
from app.analysis.jd_extractor import Category, Importance, MatchMode
from app.analysis.recommendations import ChangeType
from app.analysis.recommendations import Kind as RecommendationKind
from app.models.application import JobApplication
from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.cv import CVPassage, CVVersion
from app.models.enums import db_enum


class AnalysisMethod(StrEnum):
    RULE_ENGINE = "rule_engine"
    AI = "ai"


class Origin(StrEnum):
    RULE_ENGINE = "rule_engine"
    AI = "ai"
    USER = "user"


class SelfReport(StrEnum):
    """The candidate's own statement. Kept apart from what the CV shows."""

    UNKNOWN = "unknown"
    HAVE_NOT_ON_CV = "have_not_on_cv"
    DO_NOT_HAVE = "do_not_have"
    LEARNING = "learning"


class RequirementAnalysis(UUIDPrimaryKey, Base):
    """A snapshot: one job description compared with one CV version at one moment.

    Re-running creates a new analysis; old ones stay readable. The hashes let
    the app tell when the job description or the CV has changed since.
    """

    __tablename__ = "requirement_analyses"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    # CASCADE: evidence points at this version's passages, so it can't outlive them.
    cv_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_versions.id", ondelete="CASCADE"), index=True)
    method: Mapped[AnalysisMethod] = mapped_column(db_enum(AnalysisMethod, "analysis_method"))
    jd_sha256: Mapped[str] = mapped_column(String(64))
    cv_signature: Mapped[str] = mapped_column(String(64))  # text + section types of the CV version
    # Set in Python (not now()) so two analyses in one transaction still have an order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )

    cv_version: Mapped[CVVersion] = relationship()
    application: Mapped["JobApplication"] = relationship()
    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="analysis", order_by="JobRequirement.position", cascade="all, delete-orphan", passive_deletes=True
    )
    recommendations: Mapped[list["CVRecommendation"]] = relationship(
        order_by="CVRecommendation.position", cascade="all, delete-orphan", passive_deletes=True
    )


class JobRequirement(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job_requirements"
    __table_args__ = (CheckConstraint("jd_char_start >= 0 AND jd_char_end > jd_char_start", name="offsets"),)

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_analyses.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    jd_char_start: Mapped[int] = mapped_column(Integer)
    jd_char_end: Mapped[int] = mapped_column(Integer)
    terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    match_mode: Mapped[MatchMode] = mapped_column(db_enum(MatchMode, "match_mode"))
    category: Mapped[Category] = mapped_column(db_enum(Category, "requirement_category"))
    importance: Mapped[Importance] = mapped_column(db_enum(Importance, "requirement_importance"))
    # What the CV shows (from the matcher) ...
    evidence_status: Mapped[EvidenceStatus] = mapped_column(db_enum(EvidenceStatus, "evidence_status"))
    evidence_rationale: Mapped[str] = mapped_column(Text)
    missing_details: Mapped[str | None] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    # ... and, separately, what the candidate says.
    self_report: Mapped[SelfReport] = mapped_column(db_enum(SelfReport, "self_report"), default=SelfReport.UNKNOWN)
    origin: Mapped[Origin] = mapped_column(db_enum(Origin, "origin"), default=Origin.RULE_ENGINE)
    # True once the user changed category or importance.
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    # Not a real requirement (bad extraction): hidden and excluded from coverage, not deleted.
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)

    analysis: Mapped[RequirementAnalysis] = relationship(back_populates="requirements")
    evidence: Mapped[list["RequirementEvidence"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan", passive_deletes=True
    )


class RecommendationStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class CVRecommendation(UUIDPrimaryKey, Timestamps, Base):
    """A suggested CV change. The uploaded CV is never modified; accepted
    suggestions are a list for the candidate to apply in their own editor."""

    __tablename__ = "cv_recommendations"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_analyses.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="CASCADE"), index=True
    )
    cv_passage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cv_passages.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[RecommendationKind] = mapped_column(db_enum(RecommendationKind, "recommendation_kind"))
    change_type: Mapped[ChangeType] = mapped_column(db_enum(ChangeType, "change_type"))
    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str | None] = mapped_column(Text)
    suggested_text: Mapped[str | None] = mapped_column(Text)
    assumptions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    origin: Mapped[Origin] = mapped_column(db_enum(Origin, "origin"), default=Origin.RULE_ENGINE)
    status: Mapped[RecommendationStatus] = mapped_column(
        db_enum(RecommendationStatus, "recommendation_status"), default=RecommendationStatus.PROPOSED
    )
    # What the candidate will actually use: the suggestion as accepted, or their own edit.
    final_text: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requirement: Mapped["JobRequirement"] = relationship()


class RequirementEvidence(UUIDPrimaryKey, Base):
    """Links a requirement to one CV passage, with why it's relevant."""

    __tablename__ = "requirement_evidence"
    __table_args__ = (UniqueConstraint("requirement_id", "cv_passage_id", name="uq_requirement_evidence_pair"),)

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="CASCADE"), index=True
    )
    cv_passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_passages.id", ondelete="CASCADE"), index=True)
    relevance: Mapped[Relevance] = mapped_column(db_enum(Relevance, "evidence_relevance"))
    matched_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    note: Mapped[str] = mapped_column(String(300))

    requirement: Mapped[JobRequirement] = relationship(back_populates="evidence")
    passage: Mapped[CVPassage] = relationship()
