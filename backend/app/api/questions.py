import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import Question
from app.models.enums import RoundType
from app.models.journal import Difficulty, PracticeStatus, ResponseQuality
from app.schemas.common import Page
from app.schemas.journals import (
    AttemptCreate,
    AttemptRead,
    QuestionCreate,
    QuestionDetail,
    QuestionFacets,
    QuestionRead,
    QuestionUpdate,
)
from app.services import questions as service

router = APIRouter(prefix="/questions", tags=["questions"])


def question_read(question: Question) -> QuestionRead:
    latest = question.attempts[-1] if question.attempts else None
    application = question.application
    rnd = question.round
    return QuestionRead(
        id=question.id,
        text=question.text,
        subject=question.subject,
        topic=question.topic,
        difficulty=question.difficulty,
        original_answer=question.original_answer,
        verified_solution=question.verified_solution,
        ai_suggestion=question.ai_suggestion,
        response_quality=question.response_quality,
        time_spent_minutes=question.time_spent_minutes,
        confidence=question.confidence,
        difficulty_reason=question.difficulty_reason,
        practice_status=question.practice_status,
        asked_on=question.asked_on,
        created_at=question.created_at,
        application_id=question.application_id,
        company_name=application.company_name if application else None,
        position_title=application.position_title if application else None,
        round_id=question.round_id,
        round_name=rnd.name if rnd else None,
        round_type=rnd.round_type if rnd else None,
        journal_id=question.journal_id,
        attempt_count=len(question.attempts),
        latest_attempt=AttemptRead.model_validate(latest) if latest else None,
    )


def question_detail(question: Question) -> QuestionDetail:
    return QuestionDetail(
        **question_read(question).model_dump(),
        attempts=[AttemptRead.model_validate(a) for a in question.attempts],
    )


@router.get("", response_model=Page[QuestionRead])
def search_questions(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200, description="Matches question text, topic or subject.")] = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    position: Annotated[str | None, Query(max_length=200)] = None,
    round_type: RoundType | None = None,
    topic: Annotated[str | None, Query(max_length=100)] = None,
    difficulty: Difficulty | None = None,
    response_quality: ResponseQuality | None = None,
    practice_status: PracticeStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    application_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QuestionRead]:
    filters = service.SearchFilters(
        q=q, company=company, position=position, round_type=round_type, topic=topic, difficulty=difficulty,
        response_quality=response_quality, practice_status=practice_status, date_from=date_from, date_to=date_to,
        application_id=application_id,
    )
    items, total = service.search(db, user, filters, limit, offset)
    return Page[QuestionRead](items=[question_read(q) for q in items], total=total, limit=limit, offset=offset)


@router.get("/facets", response_model=QuestionFacets)
def question_facets(user: CurrentUser, db: DbSession) -> dict[str, list[str]]:
    return service.facets(db, user)


@router.post("", response_model=QuestionDetail, status_code=status.HTTP_201_CREATED)
def create_question(body: QuestionCreate, user: CurrentUser, db: DbSession) -> QuestionDetail:
    return question_detail(service.create_question(db, user, body.model_dump()))


@router.get("/{question_id}", response_model=QuestionDetail)
def get_question(question_id: uuid.UUID, user: CurrentUser, db: DbSession) -> QuestionDetail:
    """The question with your original answer, every later attempt, and any verified solution."""
    return question_detail(service.get_question(db, user, question_id))


@router.patch("/{question_id}", response_model=QuestionDetail)
def update_question(question_id: uuid.UUID, body: QuestionUpdate, user: CurrentUser, db: DbSession) -> QuestionDetail:
    """Topic, difficulty, verified solution, practice status… The original answer can't be edited."""
    return question_detail(service.update_question(db, user, question_id, body.changes()))


@router.post("/{question_id}/attempts", response_model=QuestionDetail, status_code=status.HTTP_201_CREATED)
def add_attempt(question_id: uuid.UUID, body: AttemptCreate, user: CurrentUser, db: DbSession) -> QuestionDetail:
    service.add_attempt(db, user, question_id, body.model_dump())
    return question_detail(service.get_question(db, user, question_id))
