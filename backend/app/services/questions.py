"""The personal question bank: create, search, re-attempt.

The original answer is a record of what happened and never changes. Later
tries are attempts; a verified solution is a separate field.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import JobApplication, Question, QuestionAttempt, RecruitmentRound, User
from app.models.enums import RoundType
from app.models.journal import Difficulty, PracticeStatus, ResponseQuality
from app.services.applications import get_application


def _like(text: str) -> str:
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def default_practice_status(quality: ResponseQuality) -> PracticeStatus:
    if quality in (ResponseQuality.PARTIAL, ResponseQuality.COULD_NOT_ANSWER):
        return PracticeStatus.TO_PRACTICE
    return PracticeStatus.NEW


def check_round(db: Session, user: User, application_id: uuid.UUID, round_id: uuid.UUID | None) -> None:
    """A round can only be linked within its own application."""
    if round_id is None:
        return
    application = get_application(db, user, application_id)
    if all(r.id != round_id for r in application.rounds):
        raise AppError(422, "round_not_in_application", "That round doesn't belong to this application.")


def build(
    user: User,
    data: dict[str, Any],
    application_id: uuid.UUID | None,
    round_id: uuid.UUID | None,
    journal_id: uuid.UUID | None = None,
    asked_on_default: date | None = None,
) -> Question:
    data = dict(data)
    # A question recorded in a journal was asked on the day of that event,
    # not the day it was typed in.
    if data.get("asked_on") is None and asked_on_default is not None:
        data["asked_on"] = asked_on_default
    if data.get("practice_status") is None:
        data["practice_status"] = default_practice_status(data["response_quality"])
    return Question(user_id=user.id, application_id=application_id, round_id=round_id, journal_id=journal_id, **data)


def create_question(db: Session, user: User, data: dict[str, Any]) -> Question:
    application_id = data.pop("application_id", None)
    round_id = data.pop("round_id", None)
    if round_id is not None and application_id is None:
        raise AppError(422, "application_required", "Choose the application this round belongs to.")
    if application_id is not None:
        get_application(db, user, application_id)
        check_round(db, user, application_id, round_id)
    question = build(user, data, application_id, round_id)
    db.add(question)
    db.commit()
    return question


def get_question(db: Session, user: User, question_id: uuid.UUID) -> Question:
    question = db.scalar(select(Question).where(Question.id == question_id, Question.user_id == user.id))
    if question is None:
        raise AppError(404, "not_found", "Question not found.")
    return question


@dataclass
class SearchFilters:
    q: str | None = None
    company: str | None = None
    position: str | None = None
    round_type: RoundType | None = None
    topic: str | None = None
    difficulty: Difficulty | None = None
    response_quality: ResponseQuality | None = None
    practice_status: PracticeStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    application_id: uuid.UUID | None = None


def search(db: Session, user: User, filters: SearchFilters, limit: int, offset: int) -> tuple[list[Question], int]:
    query = (
        select(Question)
        .outerjoin(JobApplication, Question.application_id == JobApplication.id)
        .outerjoin(RecruitmentRound, Question.round_id == RecruitmentRound.id)
        .where(Question.user_id == user.id)
    )
    if filters.q:
        pattern = _like(filters.q)
        query = query.where(
            or_(
                Question.text.ilike(pattern, escape="\\"),
                Question.topic.ilike(pattern, escape="\\"),
                Question.subject.ilike(pattern, escape="\\"),
            )
        )
    if filters.company:
        query = query.where(JobApplication.company_name.ilike(_like(filters.company), escape="\\"))
    if filters.position:
        query = query.where(JobApplication.position_title.ilike(_like(filters.position), escape="\\"))
    if filters.topic:
        query = query.where(Question.topic.ilike(_like(filters.topic), escape="\\"))
    if filters.round_type:
        query = query.where(RecruitmentRound.round_type == filters.round_type)
    for column, value in [
        (Question.difficulty, filters.difficulty),
        (Question.response_quality, filters.response_quality),
        (Question.practice_status, filters.practice_status),
        (Question.application_id, filters.application_id),
    ]:
        if value is not None:
            query = query.where(column == value)
    # "When" is the day it was asked if known, else the day it was recorded.
    when = func.coalesce(Question.asked_on, cast(Question.created_at, Date))
    if filters.date_from:
        query = query.where(when >= filters.date_from)
    if filters.date_to:
        query = query.where(when <= filters.date_to)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Question.created_at.desc(), Question.id).limit(limit).offset(offset)).all()
    return list(items), total


def facets(db: Session, user: User) -> dict[str, list[str]]:
    def distinct(column, *joins) -> list[str]:
        query = select(column).select_from(Question)
        for join in joins:
            query = query.join(*join)
        query = query.where(Question.user_id == user.id, column.is_not(None)).distinct().order_by(column)
        return [value for value in db.scalars(query).all() if value]

    application_join = (JobApplication, Question.application_id == JobApplication.id)
    return {
        "companies": distinct(JobApplication.company_name, application_join),
        "positions": distinct(JobApplication.position_title, application_join),
        "topics": distinct(Question.topic),
        "subjects": distinct(Question.subject),
    }


def update_question(db: Session, user: User, question_id: uuid.UUID, changes: dict[str, Any]) -> Question:
    question = get_question(db, user, question_id)
    for field, value in changes.items():
        setattr(question, field, value)
    db.commit()
    return question


def add_attempt(db: Session, user: User, question_id: uuid.UUID, data: dict[str, Any]) -> QuestionAttempt:
    question = get_question(db, user, question_id)
    attempt = QuestionAttempt(**data)
    question.attempts.append(attempt)
    # Practising has started. "Comfortable" is only ever the candidate's call.
    if question.practice_status in (PracticeStatus.NEW, PracticeStatus.TO_PRACTICE):
        question.practice_status = PracticeStatus.PRACTICING
    db.commit()
    return attempt
