"""Requirement analyses: run, read, correct.

Ties the pure analysis code (app/analysis) to stored records. An analysis is a
snapshot; re-running makes a new one and carries over what the user already
told us (self-reports, corrected categories, dismissed lines).
"""

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.evidence import EvidenceStatus, PassageInput, assess
from app.analysis.jd_extractor import Category, Importance, extract_requirements
from app.errors import AppError
from app.models import CVVersion, JobApplication, JobRequirement, RequirementAnalysis, RequirementEvidence, User
from app.models.analysis import AnalysisMethod, Origin, SelfReport
from app.services import recommendations
from app.services.applications import get_application

COVERAGE_EXPLANATION = (
    "Coverage = required requirements your CV visibly demonstrates ÷ all required requirements. "
    "Preferred, uncertain, dismissed and responsibility lines are left out, and partly shown "
    "requirements don't count. It measures what the CV shows, not your ability, and it does not "
    "predict whether you'll be hired."
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def cv_signature(version: CVVersion) -> str:
    """Changes when the CV's text or its section types change (both affect the verdicts)."""
    types = ",".join(section.section_type.value for section in version.sections)
    return _sha256(f"{version.raw_text}\x00{types}")


def _passages(version: CVVersion) -> list[PassageInput]:
    return [
        PassageInput(str(passage.id), passage.text, section.section_type)
        for section in version.sections
        for passage in section.passages
    ]


def _apply_assessment(requirement: JobRequirement, passages: list[PassageInput]) -> None:
    result = assess(requirement.text, requirement.category, requirement.terms, requirement.match_mode, passages)
    requirement.evidence_status = result.status
    requirement.evidence_rationale = result.rationale
    requirement.missing_details = result.missing_details
    requirement.suggested_action = result.suggested_action
    links: dict[str, Any] = {}
    for link in result.evidence:
        links.setdefault(link.passage_id, link)  # one link per passage; the strongest comes first
    requirement.evidence = [
        RequirementEvidence(
            cv_passage_id=uuid.UUID(link.passage_id),
            relevance=link.relevance,
            matched_terms=link.matched_terms,
            note=link.note[:300],
        )
        for link in links.values()
    ]


def _not_found() -> AppError:
    return AppError(404, "not_found", "Analysis not found.")


def get_analysis(db: Session, user: User, analysis_id: uuid.UUID) -> RequirementAnalysis:
    analysis = db.scalar(
        select(RequirementAnalysis)
        .join(JobApplication, RequirementAnalysis.application_id == JobApplication.id)
        .where(RequirementAnalysis.id == analysis_id, JobApplication.user_id == user.id)
    )
    if analysis is None:
        raise _not_found()
    return analysis


def list_analyses(db: Session, user: User, application_id: uuid.UUID) -> list[RequirementAnalysis]:
    get_application(db, user, application_id)  # ownership check
    return list(
        db.scalars(
            select(RequirementAnalysis)
            .where(RequirementAnalysis.application_id == application_id)
            .order_by(RequirementAnalysis.created_at.desc())
        ).all()
    )


def latest_analysis(db: Session, user: User, application_id: uuid.UUID) -> RequirementAnalysis:
    analyses = list_analyses(db, user, application_id)
    if not analyses:
        raise AppError(404, "no_analysis", "This application hasn't been analysed yet.")
    return analyses[0]


def run_analysis(db: Session, user: User, application_id: uuid.UUID) -> RequirementAnalysis:
    application = get_application(db, user, application_id)
    job_description = application.job_description or ""
    if not job_description.strip():
        raise AppError(422, "missing_job_description", "Add the job description to this application first.")
    cv = application.cv_version
    if cv is None:
        raise AppError(422, "missing_cv", "Choose which CV version this application uses first.")

    previous = list_analyses(db, user, application_id)
    carried = {r.text.strip().lower(): r for r in previous[0].requirements} if previous else {}
    passages = _passages(cv)

    analysis = RequirementAnalysis(
        application_id=application.id,
        cv_version_id=cv.id,
        method=AnalysisMethod.RULE_ENGINE,
        jd_sha256=_sha256(job_description),
        cv_signature=cv_signature(cv),
    )
    for position, extracted in enumerate(extract_requirements(job_description)):
        prior = carried.get(extracted.text.strip().lower())
        keep_edits = prior is not None and prior.user_edited
        requirement = JobRequirement(
            position=position,
            text=extracted.text,
            jd_char_start=extracted.char_start,
            jd_char_end=extracted.char_end,
            terms=extracted.terms,
            match_mode=extracted.match_mode,
            category=prior.category if keep_edits else extracted.category,
            importance=prior.importance if keep_edits else extracted.importance,
            origin=Origin.RULE_ENGINE,
            user_edited=keep_edits,
            self_report=prior.self_report if prior else SelfReport.UNKNOWN,
            dismissed=prior.dismissed if prior else False,
        )
        _apply_assessment(requirement, passages)
        analysis.requirements.append(requirement)
    recommendations.generate_for_analysis(analysis, passages, previous[0] if previous else None)
    db.add(analysis)
    db.commit()
    return analysis


def stale_reasons(analysis: RequirementAnalysis, application: JobApplication) -> list[str]:
    reasons = []
    if _sha256(application.job_description or "") != analysis.jd_sha256:
        reasons.append("The job description has changed since this analysis.")
    if application.cv_version_id != analysis.cv_version_id:
        reasons.append("The application now uses a different CV version.")
    elif cv_signature(analysis.cv_version) != analysis.cv_signature:
        reasons.append("Section types in the CV were corrected since this analysis.")
    return reasons


@dataclass
class Coverage:
    required_total: int
    demonstrated: int
    partially_demonstrated: int
    not_found_in_cv: int
    needs_verification: int
    percent: int | None
    explanation: str


def coverage(analysis: RequirementAnalysis) -> Coverage:
    required = [
        r
        for r in analysis.requirements
        if not r.dismissed and r.importance == Importance.REQUIRED and r.category != Category.RESPONSIBILITY
    ]
    count = {status: sum(1 for r in required if r.evidence_status == status) for status in EvidenceStatus}
    total = len(required)
    return Coverage(
        required_total=total,
        demonstrated=count[EvidenceStatus.DEMONSTRATED],
        partially_demonstrated=count[EvidenceStatus.PARTIALLY_DEMONSTRATED],
        not_found_in_cv=count[EvidenceStatus.NOT_FOUND_IN_CV],
        needs_verification=count[EvidenceStatus.NEEDS_VERIFICATION],
        percent=round(100 * count[EvidenceStatus.DEMONSTRATED] / total) if total else None,
        explanation=COVERAGE_EXPLANATION,
    )


def _get_requirement(db: Session, user: User, requirement_id: uuid.UUID) -> JobRequirement:
    requirement = db.scalar(
        select(JobRequirement)
        .join(RequirementAnalysis, JobRequirement.analysis_id == RequirementAnalysis.id)
        .join(JobApplication, RequirementAnalysis.application_id == JobApplication.id)
        .where(JobRequirement.id == requirement_id, JobApplication.user_id == user.id)
    )
    if requirement is None:
        raise AppError(404, "not_found", "Requirement not found.")
    return requirement


get_requirement = _get_requirement  # public name for other services (ownership-checked)


def update_requirement(db: Session, user: User, requirement_id: uuid.UUID, changes: dict[str, Any]) -> JobRequirement:
    """Self-report, dismissal, and corrections to category or importance.

    The self-report never changes the evidence verdict: the CV still shows
    what it shows. A new category is re-assessed against the same CV.
    """
    requirement = _get_requirement(db, user, requirement_id)
    category_changed = "category" in changes and changes["category"] != requirement.category
    for field in ("category", "importance"):
        if field in changes and changes[field] != getattr(requirement, field):
            setattr(requirement, field, changes[field])
            requirement.user_edited = True
    for field in ("self_report", "dismissed"):
        if field in changes:
            setattr(requirement, field, changes[field])
    passages = _passages(requirement.analysis.cv_version)
    if category_changed:
        # Remove the old links first: on flush, inserts run before deletes, and the
        # same passage linked again would break the one-link-per-passage constraint.
        requirement.evidence.clear()
        db.flush()
        _apply_assessment(requirement, passages)
    if changes:
        # A new self-report or category changes which suggestions apply.
        db.flush()
        recommendations.refresh_for_requirement(db, requirement, passages)
    db.commit()
    return requirement
