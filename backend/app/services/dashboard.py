"""The dashboard: what needs attention, what's coming, what's pending.

Computed from the user's records on each request. "Today" is passed in by the
client (its local date), so date-based items aren't off by a timezone.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.evidence import EvidenceStatus
from app.analysis.jd_extractor import Category, Importance
from app.models import (
    GapReassessment,
    JobApplication,
    Journal,
    Question,
    RecruitmentRound,
    SkillGap,
    Task,
    User,
)
from app.models.analysis import SelfReport
from app.models.enums import ApplicationStatus, RoundResult, RoundStatus
from app.models.journal import PracticeStatus
from app.models.learning import GapStatus, TaskStatus
from app.services import analyses as analyses_service

CLOSED_APPLICATION = {
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.CLOSED_UNKNOWN,
}
NOT_YET_APPLIED = {ApplicationStatus.INTERESTED, ApplicationStatus.PREPARING}
STILL_AHEAD = {RoundStatus.UPCOMING, RoundStatus.PREPARING, RoundStatus.RESCHEDULED, RoundStatus.NOT_SCHEDULED}
HORIZON_DAYS = 14


@dataclass
class Dashboard:
    today: date
    application_counts: dict[str, int]
    needs_attention: list[dict[str, Any]] = field(default_factory=list)
    upcoming_rounds: list[dict[str, Any]] = field(default_factory=list)
    upcoming_deadlines: list[dict[str, Any]] = field(default_factory=list)
    pending_results: list[dict[str, Any]] = field(default_factory=list)
    follow_ups: list[dict[str, Any]] = field(default_factory=list)
    top_tasks: list[dict[str, Any]] = field(default_factory=list)
    gap_counts: dict[str, int] = field(default_factory=dict)
    recent_reassessments: list[dict[str, Any]] = field(default_factory=list)
    questions_to_practice: list[dict[str, Any]] = field(default_factory=list)
    questions_to_practice_total: int = 0
    recent_journals: list[dict[str, Any]] = field(default_factory=list)
    analyses: list[dict[str, Any]] = field(default_factory=list)


def _app_ref(application: JobApplication) -> dict[str, Any]:
    return {
        "application_id": application.id,
        "company_name": application.company_name,
        "position_title": application.position_title,
    }


def build(db: Session, user: User, today: date) -> Dashboard:
    now = datetime.now(UTC)
    horizon = today + timedelta(days=HORIZON_DAYS)

    applications = list(
        db.scalars(
            select(JobApplication).where(JobApplication.user_id == user.id, JobApplication.archived_at.is_(None))
        ).all()
    )
    active = [a for a in applications if a.status not in CLOSED_APPLICATION]
    dashboard = Dashboard(today=today, application_counts=dict(Counter(a.status.value for a in active)))

    prep = Counter()
    prep_done = Counter()
    for task in db.scalars(select(Task).where(Task.user_id == user.id, Task.recruitment_round_id.is_not(None))).all():
        prep[task.recruitment_round_id] += 1
        if task.status == TaskStatus.COMPLETED:
            prep_done[task.recruitment_round_id] += 1

    for application in active:
        ref = _app_ref(application)
        if application.deadline and application.status in NOT_YET_APPLIED:
            if application.deadline < today:
                dashboard.needs_attention.append(
                    {**ref, "kind": "deadline_passed", "date": application.deadline,
                     "message": "The application deadline has passed and it isn't marked as applied."}
                )
            elif application.deadline <= horizon:
                dashboard.upcoming_deadlines.append({**ref, "date": application.deadline})

        for rnd in application.rounds:
            round_ref = {**ref, "round_id": rnd.id, "round_name": rnd.name, "round_type": rnd.round_type}
            if rnd.status in STILL_AHEAD and rnd.status != RoundStatus.NOT_SCHEDULED and rnd.scheduled_at and rnd.scheduled_at < now:
                dashboard.needs_attention.append(
                    {**round_ref, "kind": "round_passed", "date": rnd.scheduled_at.date(),
                     "message": "This round's date has passed. Record what happened and update its status."}
                )
            elif rnd.status in STILL_AHEAD and rnd.scheduled_at and now <= rnd.scheduled_at <= now + timedelta(days=HORIZON_DAYS):
                dashboard.upcoming_rounds.append(
                    {**round_ref, "scheduled_at": rnd.scheduled_at, "prep_total": prep[rnd.id], "prep_done": prep_done[rnd.id]}
                )
            if (
                rnd.confirmation_deadline
                and rnd.confirmation_deadline < now
                and rnd.status == RoundStatus.NOT_SCHEDULED
            ):
                dashboard.needs_attention.append(
                    {**round_ref, "kind": "confirmation_passed", "date": rnd.confirmation_deadline.date(),
                     "message": "The confirm-by deadline for this round has passed."}
                )
            if rnd.status in (RoundStatus.COMPLETED, RoundStatus.AWAITING_RESULT) and rnd.result == RoundResult.UNKNOWN:
                dashboard.pending_results.append({**round_ref, "since": (rnd.completed_at or rnd.updated_at).date()})
            if rnd.follow_up_date and rnd.follow_up_date <= today + timedelta(days=3) and rnd.result == RoundResult.UNKNOWN:
                dashboard.follow_ups.append({**round_ref, "date": rnd.follow_up_date, "overdue": rnd.follow_up_date < today})

    open_tasks = list(
        db.scalars(
            select(Task)
            .where(Task.user_id == user.id, Task.status != TaskStatus.COMPLETED)
            .order_by(Task.priority, Task.due_date.nulls_last(), Task.created_at)
        ).all()
    )
    for task in open_tasks:
        if task.due_date and task.due_date < today:
            dashboard.needs_attention.append(
                {"kind": "task_overdue", "task_id": task.id, "title": task.title, "date": task.due_date,
                 "message": "This task is past its due date."}
            )
    dashboard.top_tasks = [
        {"task_id": t.id, "title": t.title, "kind": t.kind, "status": t.status, "priority": t.priority, "due_date": t.due_date,
         "skill_gap_id": t.skill_gap_id, "application_id": t.application_id, "round_id": t.recruitment_round_id}
        for t in open_tasks[:5]
    ]

    gaps = list(db.scalars(select(SkillGap).where(SkillGap.user_id == user.id)).all())
    dashboard.gap_counts = dict(Counter(g.status.value for g in gaps))
    reassessments = db.scalars(
        select(GapReassessment)
        .join(SkillGap)
        .where(SkillGap.user_id == user.id)
        .order_by(GapReassessment.assessed_at.desc())
        .limit(3)
    ).all()
    dashboard.recent_reassessments = [
        {"skill_gap_id": r.skill_gap_id, "skill_name": r.gap.skill_name, "previous_status": r.previous_status,
         "new_status": r.new_status, "assessed_at": r.assessed_at, "summary": r.summary}
        for r in reassessments
    ]

    practice = select(Question).where(
        Question.user_id == user.id,
        Question.practice_status.in_([PracticeStatus.TO_PRACTICE, PracticeStatus.PRACTICING]),
    )
    to_practice = list(db.scalars(practice.order_by(Question.created_at.desc())).all())
    dashboard.questions_to_practice_total = len(to_practice)
    dashboard.questions_to_practice = [
        {"question_id": q.id, "text": q.text, "topic": q.topic, "practice_status": q.practice_status}
        for q in to_practice[:3]
    ]

    dashboard.recent_journals = [
        {"journal_id": j.id, "template": j.template, "round_name": j.round.name if j.round else None,
         "created_at": j.created_at, "question_count": len(j.questions), **_app_ref(j.application)}
        for j in db.scalars(
            select(Journal).where(Journal.user_id == user.id).order_by(Journal.created_at.desc()).limit(3)
        ).all()
    ]

    for application in active:
        analyses = analyses_service.list_analyses(db, user, application.id)
        if not analyses:
            continue
        latest = analyses[0]
        coverage = analyses_service.coverage(latest)
        # Required lines the CV doesn't fully show and that the candidate hasn't assessed yet.
        needs_input = sum(
            1
            for r in latest.requirements
            if not r.dismissed
            and r.importance == Importance.REQUIRED
            and r.category != Category.RESPONSIBILITY
            and r.evidence_status != EvidenceStatus.DEMONSTRATED
            and r.self_report == SelfReport.UNKNOWN
        )
        dashboard.analyses.append(
            {**_app_ref(application), "analysis_id": latest.id, "created_at": latest.created_at,
             "coverage_percent": coverage.percent, "required_total": coverage.required_total,
             "demonstrated": coverage.demonstrated, "needs_your_input": needs_input,
             "is_stale": bool(analyses_service.stale_reasons(latest, application))}
        )

    dashboard.needs_attention.sort(key=lambda item: item["date"])
    dashboard.upcoming_rounds.sort(key=lambda item: item["scheduled_at"])
    dashboard.upcoming_deadlines.sort(key=lambda item: item["date"])
    dashboard.follow_ups.sort(key=lambda item: item["date"])
    dashboard.analyses.sort(key=lambda item: item["created_at"], reverse=True)
    return dashboard


def parse_today(value: date | None) -> date:
    return value or datetime.now(UTC).date()
