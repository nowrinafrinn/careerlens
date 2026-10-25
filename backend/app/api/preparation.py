import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.analysis.preparation import SuggestionKind
from app.api.deps import CurrentUser, DbSession
from app.services import preparation as service

router = APIRouter(tags=["preparation"])


class SuggestionRead(BaseModel):
    kind: SuggestionKind
    title: str
    detail: str
    why: str
    priority: int
    is_practice_question: bool
    requirement_id: uuid.UUID | None
    skill_gap_id: uuid.UUID | None
    question_id: uuid.UUID | None
    saved_task_id: uuid.UUID | None  # set once you've saved it to your checklist


class PreparationRead(BaseModel):
    application_id: uuid.UUID
    round_id: uuid.UUID | None
    analysis_id: uuid.UUID | None
    analysis_is_stale: bool
    note: str
    suggestions: list[SuggestionRead]


@router.get("/applications/{application_id}/preparation", response_model=PreparationRead)
def preparation_suggestions(
    application_id: uuid.UUID, user: CurrentUser, db: DbSession, round_id: uuid.UUID | None = None
) -> PreparationRead:
    """Suggestions for preparing for this position (and round), from your own records.

    Computed each time, not stored. Save the ones you want as preparation tasks
    (POST /tasks with kind=preparation). Generated questions are practice questions,
    not questions the employer is known to ask.
    """
    result = service.build(db, user, application_id, round_id)
    if result.analysis_id is None:
        note = "No requirement analysis yet, so suggestions are limited to the round format. Analyse the job for more."
    elif result.analysis_is_stale:
        note = "The requirement analysis is out of date; re-run it for suggestions that match the current job and CV."
    else:
        note = "Based on the latest requirement analysis, your learning plan and your question bank."
    return PreparationRead(
        application_id=application_id,
        round_id=round_id,
        analysis_id=result.analysis_id,
        analysis_is_stale=result.analysis_is_stale,
        note=note,
        suggestions=[
            SuggestionRead(
                kind=s.kind,
                title=s.title,
                detail=s.detail,
                why=s.why,
                priority=s.priority,
                is_practice_question=s.is_practice_question,
                requirement_id=uuid.UUID(s.requirement_id) if s.requirement_id else None,
                skill_gap_id=uuid.UUID(s.skill_gap_id) if s.skill_gap_id else None,
                question_id=uuid.UUID(s.question_id) if s.question_id else None,
                saved_task_id=result.saved.get(s.title[:200]),
            )
            for s in result.suggestions
        ],
    )
