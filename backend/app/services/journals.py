"""Recruitment journals: structured reflections on a round or event."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.journal_templates import TEMPLATES, JournalTemplate, prompt_keys
from app.models import Journal, User
from app.models.enums import EventType
from app.services import questions as questions_service
from app.services.applications import get_application
from app.services.events import record_event


def _clean_responses(template: JournalTemplate, responses: dict[str, str]) -> dict[str, str]:
    unknown = sorted(set(responses) - prompt_keys(template))
    if unknown:
        raise AppError(
            422,
            "unknown_prompt",
            f"These answers don't match a prompt of the {TEMPLATES[template]['label'].lower()} template.",
            {"keys": unknown},
        )
    return {key: value.strip() for key, value in responses.items() if value and value.strip()}


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value else None


def get_journal(db: Session, user: User, journal_id: uuid.UUID) -> Journal:
    journal = db.scalar(select(Journal).where(Journal.id == journal_id, Journal.user_id == user.id))
    if journal is None:
        raise AppError(404, "not_found", "Journal not found.")
    return journal


def list_journals(db: Session, user: User, application_id: uuid.UUID | None = None) -> list[Journal]:
    query = select(Journal).where(Journal.user_id == user.id)
    if application_id is not None:
        get_application(db, user, application_id)  # ownership check: 404 for others' applications
        query = query.where(Journal.application_id == application_id)
    return list(db.scalars(query.order_by(Journal.created_at.desc())).all())


def create_journal(db: Session, user: User, data: dict[str, Any]) -> Journal:
    application = get_application(db, user, data["application_id"])
    questions_service.check_round(db, user, application.id, data.get("round_id"))
    template = data["template"]

    journal = Journal(
        user_id=user.id,
        application_id=application.id,
        round_id=data.get("round_id"),
        template=template,
        occurred_on=data.get("occurred_on"),
        responses=_clean_responses(template, data.get("responses") or {}),
        interviewer_feedback=_blank_to_none(data.get("interviewer_feedback")),
        user_interpretation=_blank_to_none(data.get("user_interpretation")),
        follow_up_actions=_blank_to_none(data.get("follow_up_actions")),
    )
    db.add(journal)
    db.flush()
    for question in data.get("questions") or []:
        journal.questions.append(
            questions_service.build(user, question, application.id, journal.round_id, journal.id, journal.occurred_on)
        )

    record_event(
        db,
        user_id=user.id,
        application_id=application.id,
        round_id=journal.round_id,
        event_type=EventType.JOURNAL_RECORDED,
        new={
            "template": template,
            "round_name": journal.round.name if journal.round else None,
            "question_count": len(journal.questions),
        },
    )
    db.commit()
    return journal


def update_journal(db: Session, user: User, journal_id: uuid.UUID, changes: dict[str, Any]) -> Journal:
    journal = get_journal(db, user, journal_id)
    if "round_id" in changes:
        questions_service.check_round(db, user, journal.application_id, changes["round_id"])
    if "responses" in changes:
        changes["responses"] = _clean_responses(journal.template, changes["responses"])
    for field in ("interviewer_feedback", "user_interpretation", "follow_up_actions"):
        if field in changes:
            changes[field] = _blank_to_none(changes[field])
    for field, value in changes.items():
        setattr(journal, field, value)
    db.commit()
    return journal


def add_questions(db: Session, user: User, journal_id: uuid.UUID, items: list[dict[str, Any]]) -> Journal:
    journal = get_journal(db, user, journal_id)
    for question in items:
        journal.questions.append(
            questions_service.build(
                user, question, journal.application_id, journal.round_id, journal.id, journal.occurred_on
            )
        )
    db.commit()
    return journal


def delete_journal(db: Session, user: User, journal_id: uuid.UUID) -> None:
    """Deletes the reflection. Its questions stay in the bank (their journal link is cleared)."""
    journal = get_journal(db, user, journal_id)
    for question in journal.questions:
        question.journal_id = None
    db.delete(journal)
    db.commit()
