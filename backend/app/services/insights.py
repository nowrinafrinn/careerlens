"""Patterns across the user's records.

Rules for every insight:
- it is computed from stored records and lists them as sources;
- it states how many observations it rests on, and below MIN_OBSERVATIONS
  it says so instead of presenting a pattern;
- it says what it's based on and carries a caveat;
- co-occurrence is never described as cause, and rejections are never read
  as a judgement of ability (outcomes aren't used here at all).
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.evidence import EvidenceStatus
from app.analysis.jd_extractor import Category, Importance
from app.models import JobApplication, Question, SkillGap, User
from app.models.journal import ResponseQuality
from app.models.learning import GapStatus, TaskStatus
from app.services import analyses as analyses_service

MIN_OBSERVATIONS = 3
_STRUGGLED = {ResponseQuality.PARTIAL, ResponseQuality.COULD_NOT_ANSWER}
_IMPROVED = {GapStatus.IMPROVING, GapStatus.RESOLVED}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _insight(
    key: str,
    category: str,
    title: str,
    statement: str,
    observations: int,
    basis: str,
    caveat: str,
    sources: list[dict[str, Any]],
    minimum: int = MIN_OBSERVATIONS,
) -> dict[str, Any]:
    sufficient = observations >= minimum
    if not sufficient:
        statement = (
            f"Not enough data yet ({_plural(observations, 'observation')}; at least {minimum} are needed "
            f"before this counts as a pattern). So far: {statement[0].lower()}{statement[1:]}"
        )
    return {
        "key": key,
        "category": category,
        "title": title,
        "statement": statement,
        "observation_count": observations,
        "sufficient_data": sufficient,
        "basis": basis,
        "caveat": caveat,
        "sources": sources,
    }


def _app_source(application: JobApplication) -> dict[str, Any]:
    return {"kind": "application", "id": application.id, "label": f"{application.position_title}, {application.company_name}"}


def build(db: Session, user: User) -> dict[str, Any]:
    insights: list[dict[str, Any]] = []
    notes: list[str] = []

    applications = list(
        db.scalars(select(JobApplication).where(JobApplication.user_id == user.id, JobApplication.archived_at.is_(None))).all()
    )
    latest = []
    for application in applications:
        analyses = analyses_service.list_analyses(db, user, application.id)
        if analyses:
            latest.append((application, analyses[0]))

    # 1 & 2: skills across the job descriptions, and how the CV shows them.
    skill_apps: dict[str, dict] = defaultdict(dict)  # skill -> {application_id: (application, requirement, status)}
    for application, analysis in latest:
        for r in analysis.requirements:
            if r.dismissed or r.category == Category.RESPONSIBILITY or r.importance == Importance.UNCERTAIN:
                continue
            for term in r.terms:
                skill_apps[term].setdefault(application.id, (application, r))

    analysed = len(latest)
    for skill, by_app in sorted(skill_apps.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        if len(by_app) < 2:
            continue
        entries = list(by_app.values())
        insights.append(
            _insight(
                f"recurring_skill:{skill.lower()}",
                "recurring_skill",
                f"{skill} recurs across your target jobs",
                f"{skill} appears in the required or preferred lines of {len(entries)} of your {analysed} analysed applications.",
                len(entries),
                "job_descriptions",
                "Counted from the job descriptions you saved; it says what these employers ask for, not what all employers want.",
                [_app_source(a) for a, _ in entries],
            )
        )
        not_shown = [(a, r) for a, r in entries if r.evidence_status != EvidenceStatus.DEMONSTRATED]
        if len(not_shown) >= 2:
            insights.append(
                _insight(
                    f"cv_evidence:{skill.lower()}",
                    "cv_evidence",
                    f"Your CV doesn't fully show {skill}",
                    f"In {len(not_shown)} of the {len(entries)} applications that ask for {skill}, the CV you used "
                    f"doesn't show it in use (partly shown or not found).",
                    len(not_shown),
                    "cv_analysis",
                    "This is about what your CV shows, not about your ability. If you have this skill, the CV suggestions "
                    "show how to make it visible.",
                    [{"kind": "requirement", "id": r.id, "label": f"“{r.text}” ({a.company_name})", "application_id": a.id} for a, r in not_shown],
                )
            )
    if analysed < MIN_OBSERVATIONS:
        notes.append(
            f"Analyse at least {MIN_OBSERVATIONS} applications to see which skills recur across your target jobs "
            f"({_plural(analysed, 'application')} analysed so far)."
        )

    # 3 & 4: topics in your question records.
    questions = list(db.scalars(select(Question).where(Question.user_id == user.id, Question.topic.is_not(None))).all())
    by_topic: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        by_topic[q.topic.strip().lower()].append(q)
    for topic_key, items in sorted(by_topic.items(), key=lambda item: -len(item[1])):
        topic = items[0].topic
        struggled = [q for q in items if q.response_quality in _STRUGGLED]
        if struggled:
            insights.append(
                _insight(
                    f"difficulty_topic:{topic_key}",
                    "difficulty_topic",
                    f"Recorded difficulty with {topic}",
                    f"You recorded {len(struggled)} of {_plural(len(items), 'question')} on {topic} as partly answered "
                    f"or not answered.",
                    len(struggled),
                    "recorded_outcomes",
                    "Based on your own records of how each question went at the time. Later attempts aren't counted here.",
                    [{"kind": "question", "id": q.id, "label": q.text[:100]} for q in struggled],
                )
            )
        companies = {q.application_id for q in items if q.application_id}
        if len(companies) >= 2:
            insights.append(
                _insight(
                    f"recurring_question_topic:{topic_key}",
                    "recurring_question_topic",
                    f"{topic} questions come up across companies",
                    f"You recorded {topic} questions in {len(companies)} different applications.",
                    len(companies),
                    "recorded_outcomes",
                    "Only counts questions you recorded; companies you didn't journal aren't included.",
                    [{"kind": "question", "id": q.id, "label": q.text[:100]} for q in items],
                )
            )
    if len(questions) < MIN_OBSERVATIONS:
        notes.append("Record questions in your journals (with a topic) to see which topics come up and where you struggle.")

    # 5, 6 & 7: the learning plan.
    gaps = list(db.scalars(select(SkillGap).where(SkillGap.user_id == user.id)).all())
    for gap in gaps:
        sources_by_app = {
            e.requirement.analysis.application_id: e.requirement.analysis.application
            for e in gap.evidence if e.requirement is not None
        } | {e.question.application_id: e.question.application for e in gap.evidence if e.question is not None and e.question.application}
        if len(sources_by_app) >= 2 and gap.status in (GapStatus.OPEN, GapStatus.IMPROVING):
            insights.append(
                _insight(
                    f"shared_priority:{gap.id}",
                    "shared_priority",
                    f"{gap.skill_name} matters for several of your roles",
                    f"Your {gap.skill_name} gap has evidence from {len(sources_by_app)} different applications.",
                    len(sources_by_app),
                    "mixed",
                    "Based on what you said about the requirements and how recorded questions went.",
                    [{"kind": "skill_gap", "id": gap.id, "label": gap.skill_name}] + [_app_source(a) for a in sources_by_app.values()],
                    minimum=2,
                )
            )

        improvements = [r for r in gap.reassessments if r.new_status in _IMPROVED and r.previous_status not in _IMPROVED]
        if improvements:
            last = improvements[-1]
            sessions = sum(len(t.attempts) for t in gap.tasks)
            cited = last.task_attempt is not None or last.question_attempt is not None
            insights.append(
                _insight(
                    f"improvement:{gap.id}",
                    "improvement",
                    f"You reassessed {gap.skill_name} as {last.new_status.value}",
                    f"You moved {gap.skill_name} from {last.previous_status.value} to {last.new_status.value}"
                    + (" and cited a practice record for it." if cited else " without citing a practice record.")
                    + f" {_plural(sessions, 'practice session')} logged for this gap so far.",
                    sessions,
                    "your_statements",
                    "This is your own reassessment. "
                    + ("One session is a weak signal; " if sessions == 1 else "")
                    + "a later real interview or assessment is the stronger test.",
                    [{"kind": "skill_gap", "id": gap.id, "label": gap.skill_name},
                     {"kind": "reassessment", "id": last.id, "label": last.summary[:100]}],
                    minimum=MIN_OBSERVATIONS,
                )
            )

    improved = []
    for gap in gaps:
        improvements = [r for r in gap.reassessments if r.new_status in _IMPROVED]
        if not improvements:
            continue
        first = improvements[0]
        done_before = [t for t in gap.tasks if t.status == TaskStatus.COMPLETED and t.updated_at <= first.assessed_at]
        if done_before:
            improved.append((gap, done_before))
    if improved:
        tasks = sum(len(done) for _, done in improved)
        insights.append(
            _insight(
                "preparation_before_improvement",
                "preparation_before_improvement",
                "Completed tasks before reported improvements",
                f"For {_plural(len(improved), 'gap')} you later reported as improved, you had completed "
                f"{_plural(tasks, 'learning task')} beforehand.",
                len(improved),
                "your_statements",
                "These happened together; that doesn't show the tasks caused the improvement. Other practice, or simply "
                "time, may have contributed.",
                [{"kind": "skill_gap", "id": g.id, "label": g.skill_name} for g, _ in improved],
            )
        )
    if not gaps:
        notes.append("Add skill gaps to your learning plan and reassess them after practice to see progress here.")

    # Sufficient insights first, then by how much they rest on.
    insights.sort(key=lambda i: (not i["sufficient_data"], -i["observation_count"], i["title"]))
    return {"minimum_observations": MIN_OBSERVATIONS, "insights": insights, "data_notes": notes}
