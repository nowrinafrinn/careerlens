"""Gathers what's on record for one application (and round) and asks the
generator for preparation suggestions. Nothing is stored until the candidate
saves a suggestion as a preparation task."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.preparation import EvidenceIn, GapIn, QuestionIn, RequirementIn, Suggestion, suggest
from app.models import Question, SkillGap, Task, User
from app.models.journal import PracticeStatus
from app.models.learning import GapStatus, TaskKind
from app.services import analyses as analyses_service
from app.services import questions as questions_service
from app.services.applications import get_application


@dataclass
class PreparationResult:
    suggestions: list[Suggestion]
    saved: dict[str, uuid.UUID]  # suggestion title -> saved preparation task id
    analysis_id: uuid.UUID | None
    analysis_is_stale: bool


def build(db: Session, user: User, application_id: uuid.UUID, round_id: uuid.UUID | None) -> PreparationResult:
    application = get_application(db, user, application_id)
    rnd = None
    if round_id is not None:
        questions_service.check_round(db, user, application.id, round_id)
        rnd = next(r for r in application.rounds if r.id == round_id)

    analyses = analyses_service.list_analyses(db, user, application.id)
    analysis = analyses[0] if analyses else None
    requirements: list[RequirementIn] = []
    terms: set[str] = set()
    if analysis is not None:
        for r in analysis.requirements:
            if r.dismissed:
                continue
            terms.update(t.lower() for t in r.terms)
            requirements.append(
                RequirementIn(
                    id=str(r.id),
                    text=r.text,
                    category=r.category,
                    importance=r.importance,
                    status=r.evidence_status,
                    self_report=r.self_report.value,
                    terms=list(r.terms),
                    evidence=[
                        EvidenceIn(link.passage.text, link.passage.section.section_type, link.relevance, list(link.matched_terms))
                        for link in r.evidence
                    ],
                )
            )

    # Open gaps that matter here: evidence from this application, or a skill this job names.
    gaps: list[GapIn] = []
    for gap in db.scalars(
        select(SkillGap).where(SkillGap.user_id == user.id, SkillGap.status.in_([GapStatus.OPEN, GapStatus.IMPROVING]))
    ).all():
        from_here = any(
            (e.requirement is not None and e.requirement.analysis.application_id == application.id)
            or (e.question is not None and e.question.application_id == application.id)
            for e in gap.evidence
        )
        if from_here or gap.skill_name.lower() in terms:
            gaps.append(GapIn(str(gap.id), gap.skill_name, gap.gap_type.value, gap.priority))
    gap_names = {g.skill_name.lower() for g in gaps}

    # Past questions worth revisiting: not yet comfortable, on a topic this job or a relevant gap names.
    questions: list[QuestionIn] = []
    for q in db.scalars(
        select(Question).where(
            Question.user_id == user.id,
            Question.practice_status != PracticeStatus.COMFORTABLE,
            Question.topic.is_not(None),
        )
    ).all():
        topic = q.topic.lower()
        if topic in gap_names or any(term in topic or topic in term for term in terms):
            questions.append(QuestionIn(str(q.id), q.text, q.topic, q.practice_status.value))

    suggestions = suggest(requirements, gaps, questions[:10], rnd.round_type if rnd else None)

    saved_query = select(Task).where(
        Task.user_id == user.id, Task.kind == TaskKind.PREPARATION, Task.application_id == application.id
    )
    if round_id is not None:
        saved_query = saved_query.where(Task.recruitment_round_id == round_id)
    saved = {task.title: task.id for task in db.scalars(saved_query).all()}

    stale = False
    if analysis is not None:
        stale = bool(analyses_service.stale_reasons(analysis, application))
    return PreparationResult(suggestions, saved, analysis.id if analysis else None, stale)
