import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.ai.provider import AIProvider, get_ai_provider
from app.api.deps import CurrentUser, DbSession
from app.models import JobRequirement, RequirementAnalysis
from app.models.analysis import AnalysisMethod
from app.schemas.analysis import (
    AnalysisRead,
    AnalysisSummary,
    CoverageRead,
    EvidenceRead,
    RequirementRead,
    RequirementUpdate,
)
from app.schemas.cv import CVVersionRef
from app.services import analyses as service
from app.services import learning as learning_service
from app.services.applications import get_application

router = APIRouter(tags=["analysis"])


def _requirement(requirement: JobRequirement, skill_gap_id: uuid.UUID | None = None) -> RequirementRead:
    evidence = [
        EvidenceRead(
            passage_id=link.passage.id,
            passage_text=link.passage.text,
            section_type=link.passage.section.section_type,
            char_start=link.passage.char_start,
            char_end=link.passage.char_end,
            relevance=link.relevance,
            matched_terms=link.matched_terms,
            note=link.note,
        )
        for link in requirement.evidence
    ]
    fields = {
        name: getattr(requirement, name) for name in RequirementRead.model_fields if name not in {"evidence", "skill_gap_id"}
    }
    return RequirementRead(**fields, evidence=evidence, skill_gap_id=skill_gap_id)


def _summary(analysis: RequirementAnalysis) -> dict:
    return {
        "id": analysis.id,
        "application_id": analysis.application_id,
        "method": analysis.method,
        "created_at": analysis.created_at,
        "cv_version": CVVersionRef.model_validate(analysis.cv_version),
        "coverage": CoverageRead(**asdict(service.coverage(analysis))),
    }


def _read(db: DbSession, user: CurrentUser, analysis: RequirementAnalysis) -> AnalysisRead:
    application = get_application(db, user, analysis.application_id)
    reasons = service.stale_reasons(analysis, application)
    gaps = learning_service.gap_ids_for_requirements(db, user, analysis.requirements)
    return AnalysisRead(
        **_summary(analysis),
        is_stale=bool(reasons),
        stale_reasons=reasons,
        notes=list(analysis.notes or []),
        requirements=[_requirement(r, gaps.get(r.id)) for r in analysis.requirements],
    )


@router.post("/applications/{application_id}/analyses", response_model=AnalysisRead, status_code=status.HTTP_201_CREATED)
def run_analysis(
    application_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    provider: Annotated[AIProvider | None, Depends(get_ai_provider)],
    method: AnalysisMethod = AnalysisMethod.RULE_ENGINE,
) -> AnalysisRead:
    """Extracts the job's requirements and checks each against the application's CV version.

    `rule_engine` (default): nothing leaves the server. `ai`: the job's requirements and the
    CV's passages (not its contact header) go to the configured AI provider; needs the user's
    consent. AI verdicts are validated and any that fail fall back to the rule engine, with a
    note saying why. Earlier analyses are kept.
    """
    return _read(db, user, service.run_analysis(db, user, application_id, method, provider))


@router.get("/applications/{application_id}/analyses", response_model=list[AnalysisSummary])
def list_analyses(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[dict]:
    return [_summary(a) for a in service.list_analyses(db, user, application_id)]


@router.get("/applications/{application_id}/analyses/latest", response_model=AnalysisRead)
def latest_analysis(application_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AnalysisRead:
    """The most recent analysis, flagged as stale if the job description or CV changed since."""
    return _read(db, user, service.latest_analysis(db, user, application_id))


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
def get_analysis(analysis_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AnalysisRead:
    return _read(db, user, service.get_analysis(db, user, analysis_id))


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
def update_requirement(requirement_id: uuid.UUID, body: RequirementUpdate, user: CurrentUser, db: DbSession) -> RequirementRead:
    """Your own assessment (self_report), dismissal, or a corrected category/importance.

    The self-report is stored next to the CV verdict and never replaces it.
    """
    requirement = service.update_requirement(db, user, requirement_id, body.changes())
    gaps = learning_service.gap_ids_for_requirements(db, user, [requirement])
    return _requirement(requirement, gaps.get(requirement.id))
