import uuid
from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import GapReassessment, SkillGap, Task
from app.models.journal import ResponseQuality
from app.models.learning import GapStatus, TaskKind, TaskStatus
from app.schemas.learning import (
    CitableQuestionAttempt,
    GapCreate,
    GapDetail,
    GapEvidenceRead,
    GapFromSource,
    GapSummary,
    GapUpdate,
    ReassessmentCreate,
    ReassessmentRead,
    TaskAttemptCreate,
    TaskAttemptRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services import learning as service

router = APIRouter(tags=["learning"])


def task_read(task: Task) -> TaskRead:
    application = task.application
    return TaskRead(
        id=task.id,
        kind=task.kind,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        why=task.why,
        skill_gap_id=task.skill_gap_id,
        skill_name=task.skill_gap.skill_name if task.skill_gap else None,
        job_requirement_id=task.job_requirement_id,
        requirement_text=task.requirement.text if task.requirement else None,
        application_id=task.application_id,
        application_label=f"{application.position_title}, {application.company_name}" if application else None,
        recruitment_round_id=task.recruitment_round_id,
        round_name=task.round.name if task.round else None,
        question_id=task.question_id,
        question_text=task.question.text if task.question else None,
        created_at=task.created_at,
        attempts=[TaskAttemptRead.model_validate(a) for a in task.attempts],
    )


def _cited(r: GapReassessment) -> str | None:
    if r.task_attempt is not None:
        a = r.task_attempt
        minutes = f", {a.duration_minutes} min" if a.duration_minutes is not None else ""
        return f"Task “{a.task.title}”: {a.outcome.value}{minutes}"
    if r.question_attempt is not None:
        a = r.question_attempt
        text = a.question.text if len(a.question.text) <= 80 else a.question.text[:79].rstrip() + "…"
        return f"Question “{text}”: {_QUALITY_WORDS[a.response_quality]}"
    return None


_QUALITY_WORDS = {
    ResponseQuality.CONFIDENT: "answered confidently",
    ResponseQuality.PARTIAL: "partly answered",
    ResponseQuality.COULD_NOT_ANSWER: "couldn't answer",
    ResponseQuality.NOT_ATTEMPTED: "not attempted",
}


def _summary_fields(gap: SkillGap) -> dict:
    applications = {
        e.requirement.analysis.application_id for e in gap.evidence if e.requirement is not None
    } | {e.question.application_id for e in gap.evidence if e.question is not None and e.question.application_id}
    return {
        "id": gap.id,
        "skill_name": gap.skill_name,
        "gap_type": gap.gap_type,
        "importance": gap.importance,
        "confidence": gap.confidence,
        "status": gap.status,
        "priority": gap.priority,
        "target_date": gap.target_date,
        "recommended_action": gap.recommended_action,
        "created_at": gap.created_at,
        "updated_at": gap.updated_at,
        "evidence_count": len(gap.evidence),
        "application_count": len(applications),
        "evidence_by_basis": dict(Counter(e.basis.value for e in gap.evidence)),
        "task_count": len(gap.tasks),
        "completed_task_count": sum(1 for t in gap.tasks if t.status == TaskStatus.COMPLETED),
    }


def gap_detail(gap: SkillGap) -> GapDetail:
    evidence = []
    for e in gap.evidence:
        application = (
            e.requirement.analysis.application if e.requirement is not None
            else e.question.application if e.question is not None else None
        )
        evidence.append(
            GapEvidenceRead(
                id=e.id,
                basis=e.basis,
                note=e.note,
                created_at=e.created_at,
                requirement_id=e.requirement_id,
                requirement_text=e.requirement.text if e.requirement else None,
                application_id=application.id if application else None,
                company_name=application.company_name if application else None,
                position_title=application.position_title if application else None,
                question_id=e.question_id,
                question_text=e.question.text if e.question else None,
                journal_id=e.journal_id,
            )
        )
    return GapDetail(
        **_summary_fields(gap),
        notes=gap.notes,
        evidence=evidence,
        reassessments=[
            ReassessmentRead(
                id=r.id,
                assessed_at=r.assessed_at,
                previous_status=r.previous_status,
                new_status=r.new_status,
                confidence=r.confidence,
                summary=r.summary,
                task_attempt_id=r.task_attempt_id,
                question_attempt_id=r.question_attempt_id,
                cited=_cited(r),
            )
            for r in gap.reassessments
        ],
        tasks=[task_read(t) for t in gap.tasks],
        question_attempts=_question_attempts(gap),
    )


def _question_attempts(gap: SkillGap) -> list[CitableQuestionAttempt]:
    """Re-attempts of the questions behind this gap (its evidence and its tasks)."""
    questions = {e.question.id: e.question for e in gap.evidence if e.question is not None}
    questions |= {t.question.id: t.question for t in gap.tasks if t.question is not None}
    attempts = [
        CitableQuestionAttempt(
            id=a.id,
            question_id=q.id,
            question_text=q.text,
            attempted_at=a.attempted_at,
            response_quality=a.response_quality,
        )
        for q in questions.values()
        for a in q.attempts
    ]
    return sorted(attempts, key=lambda a: a.attempted_at, reverse=True)


# --- gaps ----------------------------------------------------------------------------


@router.get("/skill-gaps", response_model=list[GapSummary])
def list_gaps(user: CurrentUser, db: DbSession, status_: Annotated[GapStatus | None, Query(alias="status")] = None) -> list[GapSummary]:
    """Your skill gaps, ordered by what to work on next: open first, then your priority,
    importance and how much evidence supports each one."""
    return [GapSummary(**_summary_fields(g)) for g in service.list_gaps(db, user, status_)]


@router.post("/skill-gaps", response_model=GapDetail, status_code=status.HTTP_201_CREATED)
def create_gap(body: GapCreate, user: CurrentUser, db: DbSession) -> GapDetail:
    return gap_detail(service.create_gap(db, user, body.model_dump()))


@router.post("/requirements/{requirement_id}/skill-gap", response_model=GapDetail)
def gap_from_requirement(requirement_id: uuid.UUID, body: GapFromSource, user: CurrentUser, db: DbSession) -> GapDetail:
    """Adds a requirement to your learning plan. Needs your own assessment of “I don't have this
    yet” or “I'm learning this”: missing from the CV alone is not evidence of a gap."""
    return gap_detail(service.gap_from_requirement(db, user, requirement_id, body.skill_name))


@router.post("/questions/{question_id}/skill-gap", response_model=GapDetail)
def gap_from_question(question_id: uuid.UUID, body: GapFromSource, user: CurrentUser, db: DbSession) -> GapDetail:
    """Adds a question you struggled with to your learning plan (as evidence for a gap)."""
    return gap_detail(service.gap_from_question(db, user, question_id, body.skill_name))


@router.get("/skill-gaps/{gap_id}", response_model=GapDetail)
def get_gap(gap_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GapDetail:
    return gap_detail(service.get_gap(db, user, gap_id))


@router.patch("/skill-gaps/{gap_id}", response_model=GapDetail)
def update_gap(gap_id: uuid.UUID, body: GapUpdate, user: CurrentUser, db: DbSession) -> GapDetail:
    return gap_detail(service.update_gap(db, user, gap_id, body.changes()))


@router.post("/skill-gaps/{gap_id}/reassessments", response_model=GapDetail, status_code=status.HTTP_201_CREATED)
def reassess(gap_id: uuid.UUID, body: ReassessmentCreate, user: CurrentUser, db: DbSession) -> GapDetail:
    """Records whether the gap has improved, optionally citing the attempt that shows it.
    This is the only way to change a gap's status."""
    return gap_detail(service.reassess(db, user, gap_id, body.model_dump()))


# --- tasks ---------------------------------------------------------------------------


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    user: CurrentUser,
    db: DbSession,
    kind: TaskKind | None = None,
    status_: Annotated[TaskStatus | None, Query(alias="status")] = None,
    skill_gap_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    recruitment_round_id: uuid.UUID | None = None,
) -> list[TaskRead]:
    filters = {"kind": kind, "status": status_, "skill_gap_id": skill_gap_id, "application_id": application_id,
               "recruitment_round_id": recruitment_round_id}
    return [task_read(t) for t in service.list_tasks(db, user, filters)]


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, user: CurrentUser, db: DbSession) -> TaskRead:
    return task_read(service.create_task(db, user, body.model_dump()))


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: uuid.UUID, body: TaskUpdate, user: CurrentUser, db: DbSession) -> TaskRead:
    return task_read(service.update_task(db, user, task_id, body.changes()))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    service.delete_task(db, user, task_id)


@router.post("/tasks/{task_id}/attempts", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def add_task_attempt(task_id: uuid.UUID, body: TaskAttemptCreate, user: CurrentUser, db: DbSession) -> TaskRead:
    """Logs a practice session. A planned task becomes in progress; completion is your call."""
    return task_read(service.add_task_attempt(db, user, task_id, body.model_dump()))
