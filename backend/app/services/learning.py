"""Skill gaps, learning tasks and reassessments.

The rules that keep this evidence-based:
- a gap from a job requirement needs the candidate's own statement
  ("I don't have this yet" / "I'm learning this"); "not found in CV" alone
  is not enough;
- a gap from a question needs a recorded difficulty (partly answered or
  not answered);
- the gap type is the candidate's diagnosis; nothing here sets it;
- status changes only through reassessments, which are append-only.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.jd_extractor import Importance
from app.errors import AppError
from app.models import (
    GapEvidence,
    GapReassessment,
    JobRequirement,
    Question,
    QuestionAttempt,
    RequirementAnalysis,
    SkillGap,
    Task,
    TaskAttempt,
    User,
)
from app.models.analysis import SelfReport
from app.models.journal import ResponseQuality
from app.models.learning import EvidenceBasis, GapStatus, Level, TaskStatus
from app.services import analyses as analyses_service
from app.services import questions as questions_service
from app.services import rounds as rounds_service
from app.services.applications import get_application

_LEVEL_RANK = {Level.LOW: 0, Level.MEDIUM: 1, Level.HIGH: 2}
_IMPORTANCE_FROM_REQUIREMENT = {
    Importance.REQUIRED: Level.HIGH,
    Importance.PREFERRED: Level.MEDIUM,
    Importance.UNCERTAIN: Level.LOW,
}
_STRUGGLED = {ResponseQuality.PARTIAL, ResponseQuality.COULD_NOT_ANSWER}
# Open and improving are both "active"; between active gaps, the candidate's priority decides.
_STATUS_GROUP = {GapStatus.OPEN: 0, GapStatus.IMPROVING: 0, GapStatus.RESOLVED: 1, GapStatus.DISMISSED: 2}


# --- gaps ----------------------------------------------------------------------------


def get_gap(db: Session, user: User, gap_id: uuid.UUID) -> SkillGap:
    gap = db.scalar(select(SkillGap).where(SkillGap.id == gap_id, SkillGap.user_id == user.id))
    if gap is None:
        raise AppError(404, "not_found", "Skill gap not found.")
    return gap


def _find_by_skill(db: Session, user: User, skill_name: str) -> SkillGap | None:
    return db.scalar(
        select(SkillGap).where(SkillGap.user_id == user.id, func.lower(SkillGap.skill_name) == skill_name.lower())
    )


def _gap_for(db: Session, user: User, skill_name: str, importance: Level) -> SkillGap:
    """The user's gap for this skill, created if needed; importance only ever goes up."""
    gap = _find_by_skill(db, user, skill_name)
    if gap is None:
        gap = SkillGap(user_id=user.id, skill_name=skill_name, importance=importance)
        db.add(gap)
    elif _LEVEL_RANK[importance] > _LEVEL_RANK[gap.importance]:
        gap.importance = importance
    return gap


def gap_from_requirement(db: Session, user: User, requirement_id: uuid.UUID, skill_name: str | None) -> SkillGap:
    requirement = analyses_service.get_requirement(db, user, requirement_id)
    if requirement.self_report not in (SelfReport.DO_NOT_HAVE, SelfReport.LEARNING):
        raise AppError(
            422,
            "self_report_required",
            "Say first whether you have this skill. A requirement your CV doesn't mention isn't "
            "evidence that you lack it, so it only becomes a learning goal on your word.",
        )
    name = skill_name or (requirement.terms[0] if requirement.terms else requirement.text[:100])
    gap = _gap_for(db, user, name, _IMPORTANCE_FROM_REQUIREMENT[requirement.importance])
    application_id = requirement.analysis.application_id

    # Re-runs create new requirement rows; the same line of the same job is the same evidence.
    already = any(
        e.requirement is not None
        and e.requirement.analysis.application_id == application_id
        and e.requirement.text.strip().lower() == requirement.text.strip().lower()
        for e in gap.evidence
    )
    if not already:
        said = "I'm learning this" if requirement.self_report == SelfReport.LEARNING else "I don't have this yet"
        gap.evidence.append(
            GapEvidence(requirement=requirement, basis=EvidenceBasis.USER_CONFIRMED, note=f"You said “{said}” for this requirement.")
        )
    db.commit()
    return gap


def gap_from_question(db: Session, user: User, question_id: uuid.UUID, skill_name: str | None) -> SkillGap:
    question = questions_service.get_question(db, user, question_id)
    outcomes = [question.response_quality, *(a.response_quality for a in question.attempts)]
    if not any(outcome in _STRUGGLED for outcome in outcomes):
        raise AppError(
            422,
            "no_difficulty_recorded",
            "This question wasn't recorded as partly answered or unanswered, so there's no evidence of a gap.",
        )
    name = skill_name or question.topic
    if not name:
        raise AppError(422, "skill_name_required", "This question has no topic. Name the skill it tests.")
    gap = _gap_for(db, user, name, Level.MEDIUM)
    if not any(e.question_id == question.id for e in gap.evidence):
        gap.evidence.append(
            GapEvidence(
                question=question,
                journal_id=question.journal_id,
                basis=EvidenceBasis.RECORDED_OUTCOME,
                note=f"Recorded as “{question.response_quality.value.replace('_', ' ')}”"
                + (f": {question.difficulty_reason}" if question.difficulty_reason else "."),
            )
        )
    db.commit()
    return gap


def create_gap(db: Session, user: User, data: dict[str, Any]) -> SkillGap:
    existing = _find_by_skill(db, user, data["skill_name"])
    if existing is not None:
        raise AppError(409, "gap_exists", f"You already have a gap for “{existing.skill_name}”.", {"skill_gap_id": str(existing.id)})
    reason = data.pop("reason")
    gap = SkillGap(user_id=user.id, **data)
    gap.evidence.append(GapEvidence(basis=EvidenceBasis.USER_CONFIRMED, note=reason))
    db.add(gap)
    db.commit()
    return gap


def list_gaps(db: Session, user: User, status: GapStatus | None = None) -> list[SkillGap]:
    query = select(SkillGap).where(SkillGap.user_id == user.id)
    if status is not None:
        query = query.where(SkillGap.status == status)
    gaps = list(db.scalars(query).all())
    # What to learn next: active gaps first, then your priority, importance, open before
    # improving, and how much evidence there is.
    gaps.sort(
        key=lambda g: (
            _STATUS_GROUP[g.status],
            g.priority,
            -_LEVEL_RANK[g.importance],
            g.status != GapStatus.OPEN,
            -len(g.evidence),
            g.skill_name.lower(),
        )
    )
    return gaps


def update_gap(db: Session, user: User, gap_id: uuid.UUID, changes: dict[str, Any]) -> SkillGap:
    gap = get_gap(db, user, gap_id)
    new_name = changes.get("skill_name")
    if new_name and new_name.lower() != gap.skill_name.lower():
        clash = _find_by_skill(db, user, new_name)
        if clash is not None:
            raise AppError(409, "gap_exists", f"You already have a gap for “{clash.skill_name}”.", {"skill_gap_id": str(clash.id)})
    for field, value in changes.items():
        setattr(gap, field, value)
    db.commit()
    return gap


def reassess(db: Session, user: User, gap_id: uuid.UUID, data: dict[str, Any]) -> SkillGap:
    gap = get_gap(db, user, gap_id)
    if data.get("task_attempt_id") is not None:
        owned = db.scalar(
            select(TaskAttempt.id).join(Task).where(TaskAttempt.id == data["task_attempt_id"], Task.user_id == user.id)
        )
        if owned is None:
            raise AppError(404, "not_found", "Task attempt not found.")
    if data.get("question_attempt_id") is not None:
        owned = db.scalar(
            select(QuestionAttempt.id)
            .join(Question)
            .where(QuestionAttempt.id == data["question_attempt_id"], Question.user_id == user.id)
        )
        if owned is None:
            raise AppError(404, "not_found", "Question attempt not found.")

    gap.reassessments.append(
        GapReassessment(
            previous_status=gap.status,
            new_status=data["new_status"],
            confidence=data["confidence"],
            summary=data["summary"],
            task_attempt_id=data.get("task_attempt_id"),
            question_attempt_id=data.get("question_attempt_id"),
        )
    )
    gap.status = data["new_status"]
    gap.confidence = data["confidence"]
    db.commit()
    return gap


def gap_ids_for_requirements(db: Session, user: User, requirements: list[JobRequirement]) -> dict[uuid.UUID, uuid.UUID]:
    """Which gap (if any) each requirement already feeds, matching re-runs by job and text."""
    if not requirements:
        return {}
    rows = db.execute(
        select(GapEvidence.skill_gap_id, RequirementAnalysis.application_id, JobRequirement.text)
        .join(JobRequirement, GapEvidence.requirement_id == JobRequirement.id)
        .join(RequirementAnalysis, JobRequirement.analysis_id == RequirementAnalysis.id)
        .join(SkillGap, GapEvidence.skill_gap_id == SkillGap.id)
        .where(SkillGap.user_id == user.id)
    ).all()
    by_key = {(application_id, text.strip().lower()): gap_id for gap_id, application_id, text in rows}
    return {
        r.id: by_key[key]
        for r in requirements
        if (key := (r.analysis.application_id, r.text.strip().lower())) in by_key
    }


def gap_id_for_question(db: Session, user: User, question_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(
        select(GapEvidence.skill_gap_id)
        .join(SkillGap)
        .where(GapEvidence.question_id == question_id, SkillGap.user_id == user.id)
        .limit(1)
    )


# --- tasks ---------------------------------------------------------------------------


def get_task(db: Session, user: User, task_id: uuid.UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    if task is None:
        raise AppError(404, "not_found", "Task not found.")
    return task


def create_task(db: Session, user: User, data: dict[str, Any]) -> Task:
    # Every link must point at the user's own records.
    gap = get_gap(db, user, data["skill_gap_id"]) if data.get("skill_gap_id") else None
    if data.get("job_requirement_id"):
        analyses_service.get_requirement(db, user, data["job_requirement_id"])
    if data.get("question_id"):
        questions_service.get_question(db, user, data["question_id"])
    if data.get("recruitment_round_id"):
        rnd = rounds_service.get_round(db, user, data["recruitment_round_id"])
        if data.get("application_id") and data["application_id"] != rnd.application_id:
            raise AppError(422, "round_not_in_application", "That round doesn't belong to this application.")
        data["application_id"] = rnd.application_id
    elif data.get("application_id"):
        get_application(db, user, data["application_id"])

    if not data.get("why") and gap is not None:
        data["why"] = f"Learning goal: {gap.skill_name}."
    data.pop("skill_gap_id", None)
    task = Task(user_id=user.id, **data)
    if gap is not None:
        gap.tasks.append(task)  # through the relationship, so a loaded gap sees its new task
    db.add(task)
    db.commit()
    return task


def list_tasks(db: Session, user: User, filters: dict[str, Any]) -> list[Task]:
    query = select(Task).where(Task.user_id == user.id)
    for field in ("kind", "status", "skill_gap_id", "application_id", "recruitment_round_id"):
        if filters.get(field) is not None:
            query = query.where(getattr(Task, field) == filters[field])
    return list(db.scalars(query.order_by(Task.priority, Task.due_date.nulls_last(), Task.created_at)).all())


def update_task(db: Session, user: User, task_id: uuid.UUID, changes: dict[str, Any]) -> Task:
    task = get_task(db, user, task_id)
    for field, value in changes.items():
        setattr(task, field, value)
    db.commit()
    return task


def delete_task(db: Session, user: User, task_id: uuid.UUID) -> None:
    db.delete(get_task(db, user, task_id))
    db.commit()


def add_task_attempt(db: Session, user: User, task_id: uuid.UUID, data: dict[str, Any]) -> Task:
    task = get_task(db, user, task_id)
    task.attempts.append(TaskAttempt(**data))
    if task.status == TaskStatus.PLANNED:
        task.status = TaskStatus.IN_PROGRESS
    db.commit()
    return task
