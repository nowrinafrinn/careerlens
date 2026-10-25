"""Stores and updates CV recommendations for an analysis.

Generated suggestions start as "proposed". The candidate accepts, edits or
rejects each one; those decisions are never overwritten by regeneration.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.evidence import PassageInput
from app.analysis.recommendations import EvidenceInput, RequirementInput, generate, new_numbers
from app.errors import AppError
from app.models import CVRecommendation, JobApplication, JobRequirement, RequirementAnalysis, User
from app.models.analysis import RecommendationStatus


def _input(requirement: JobRequirement, passages: dict[str, PassageInput]) -> RequirementInput:
    return RequirementInput(
        text=requirement.text,
        category=requirement.category,
        importance=requirement.importance,
        status=requirement.evidence_status,
        self_report=requirement.self_report.value,
        terms=list(requirement.terms),
        match_mode=requirement.match_mode,
        evidence=[
            EvidenceInput(
                str(link.cv_passage_id),
                passages[str(link.cv_passage_id)].text,
                passages[str(link.cv_passage_id)].section_type,
                link.relevance,
                list(link.matched_terms),
                link.note,
            )
            for link in requirement.evidence
            if str(link.cv_passage_id) in passages
        ],
    )


def _key(kind, change_type, title: str, original_text: str | None) -> tuple:
    return (str(kind), str(change_type), title, original_text)


def _decided(rec: CVRecommendation) -> bool:
    return rec.status != RecommendationStatus.PROPOSED


def generate_for_analysis(
    analysis: RequirementAnalysis, passages: list[PassageInput], previous: RequirementAnalysis | None
) -> None:
    """Fills `analysis.recommendations`; decisions on matching suggestions in `previous` carry over."""
    by_id = {p.id: p for p in passages}
    carried = {_key(r.kind, r.change_type, r.title, r.original_text): r for r in (previous.recommendations if previous else [])}
    seen: set[tuple] = set()
    for requirement in analysis.requirements:
        if requirement.dismissed:
            continue
        for draft in generate(_input(requirement, by_id)):
            key = _key(draft.kind, draft.change_type, draft.title, draft.original_text)
            if key in seen:
                continue
            seen.add(key)
            prior = carried.get(key)
            analysis.recommendations.append(
                CVRecommendation(
                    requirement=requirement,
                    cv_passage_id=uuid.UUID(draft.passage_id) if draft.passage_id else None,
                    position=len(analysis.recommendations),
                    kind=draft.kind,
                    change_type=draft.change_type,
                    title=draft.title[:300],
                    rationale=draft.rationale,
                    original_text=draft.original_text,
                    suggested_text=draft.suggested_text,
                    assumptions=draft.assumptions,
                    terms=draft.terms,
                    status=prior.status if prior else RecommendationStatus.PROPOSED,
                    final_text=prior.final_text if prior else None,
                    decided_at=prior.decided_at if prior else None,
                )
            )


def refresh_for_requirement(db: Session, requirement: JobRequirement, passages: list[PassageInput]) -> None:
    """After the candidate changes a requirement (self-report, category…), update its suggestions.

    Undecided suggestions that no longer apply are removed; decided ones stay.
    """
    analysis = requirement.analysis
    mine = [r for r in analysis.recommendations if r.requirement_id == requirement.id]
    others = {_key(r.kind, r.change_type, r.title, r.original_text) for r in analysis.recommendations if r.requirement_id != requirement.id}
    drafts = [] if requirement.dismissed else generate(_input(requirement, {p.id: p for p in passages}))
    wanted = {_key(d.kind, d.change_type, d.title, d.original_text): d for d in drafts}

    for rec in mine:
        if not _decided(rec) and _key(rec.kind, rec.change_type, rec.title, rec.original_text) not in wanted:
            analysis.recommendations.remove(rec)
    existing = {_key(r.kind, r.change_type, r.title, r.original_text) for r in analysis.recommendations}
    position = max((r.position for r in analysis.recommendations), default=-1) + 1
    for key, draft in wanted.items():
        if key in existing or key in others:
            continue
        analysis.recommendations.append(
            CVRecommendation(
                requirement=requirement,
                cv_passage_id=uuid.UUID(draft.passage_id) if draft.passage_id else None,
                position=position,
                kind=draft.kind,
                change_type=draft.change_type,
                title=draft.title[:300],
                rationale=draft.rationale,
                original_text=draft.original_text,
                suggested_text=draft.suggested_text,
                assumptions=draft.assumptions,
                terms=draft.terms,
            )
        )
        position += 1
    db.flush()


def get_recommendation(db: Session, user: User, recommendation_id: uuid.UUID) -> CVRecommendation:
    rec = db.scalar(
        select(CVRecommendation)
        .join(RequirementAnalysis, CVRecommendation.analysis_id == RequirementAnalysis.id)
        .join(JobApplication, RequirementAnalysis.application_id == JobApplication.id)
        .where(CVRecommendation.id == recommendation_id, JobApplication.user_id == user.id)
    )
    if rec is None:
        raise AppError(404, "not_found", "Recommendation not found.")
    return rec


def decide(db: Session, user: User, recommendation_id: uuid.UUID, changes: dict[str, Any]) -> CVRecommendation:
    rec = get_recommendation(db, user, recommendation_id)
    status = changes["status"]
    final_text = (changes.get("final_text") or "").strip() or None

    if status == RecommendationStatus.EDITED and not final_text:
        raise AppError(422, "final_text_required", "Write your version of the text, or accept or reject the suggestion.")
    rec.status = status
    rec.final_text = {
        RecommendationStatus.ACCEPTED: rec.suggested_text,
        RecommendationStatus.EDITED: final_text,
    }.get(status)
    rec.decided_at = None if status == RecommendationStatus.PROPOSED else datetime.now(UTC)
    db.commit()
    return rec


def number_warnings(rec: CVRecommendation) -> list[str]:
    """Numbers in the text the candidate will use that weren't in their original wording."""
    text = rec.final_text if rec.final_text is not None else rec.suggested_text
    return new_numbers(rec.original_text, text)
