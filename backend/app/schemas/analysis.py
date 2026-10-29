import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.analysis.cv_parser import SectionType
from app.analysis.evidence import EvidenceStatus, Relevance
from app.analysis.jd_extractor import Category, Importance, MatchMode
from app.models.analysis import AnalysisMethod, Origin, SelfReport
from app.schemas.common import PartialUpdate
from app.schemas.cv import CVVersionRef


class EvidenceRead(BaseModel):
    """A CV passage cited for a requirement, with where it sits in the CV."""

    passage_id: uuid.UUID
    passage_text: str
    section_type: SectionType
    char_start: int
    char_end: int
    relevance: Relevance
    matched_terms: list[str]
    note: str


class RequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    text: str
    jd_char_start: int
    jd_char_end: int
    terms: list[str]
    match_mode: MatchMode
    category: Category
    importance: Importance
    evidence_status: EvidenceStatus
    evidence_rationale: str
    missing_details: str | None
    suggested_action: str
    self_report: SelfReport
    origin: Origin  # who extracted the line from the job description
    assessed_by: AnalysisMethod  # who judged the CV evidence (AI verdicts passed validation)
    user_edited: bool
    dismissed: bool
    evidence: list[EvidenceRead]
    skill_gap_id: uuid.UUID | None = None  # the learning-plan gap this requirement feeds, if any


class CoverageRead(BaseModel):
    required_total: int
    demonstrated: int
    partially_demonstrated: int
    not_found_in_cv: int
    needs_verification: int
    percent: int | None
    explanation: str


class AnalysisSummary(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    method: AnalysisMethod
    created_at: datetime
    cv_version: CVVersionRef
    coverage: CoverageRead


class AnalysisRead(AnalysisSummary):
    is_stale: bool
    stale_reasons: list[str]
    notes: list[str]  # how it was made, e.g. where the AI's verdict wasn't used and why
    requirements: list[RequirementRead]


class RequirementUpdate(PartialUpdate):
    model_config = ConfigDict(extra="forbid")
    non_nullable = frozenset({"category", "importance", "self_report", "dismissed"})

    category: Category | None = None
    importance: Importance | None = None
    self_report: SelfReport | None = None
    dismissed: bool | None = None
