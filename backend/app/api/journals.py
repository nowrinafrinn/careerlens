import uuid

from fastapi import APIRouter, status
from pydantic import TypeAdapter

from app.api.deps import CurrentUser, DbSession
from app.api.questions import question_read
from app.journal_templates import TEMPLATES
from app.models import Journal
from app.schemas.journals import JournalCreate, JournalRead, JournalUpdate, QuestionFields, TemplateRead
from app.services import journals as service

router = APIRouter(tags=["journals"])


def journal_read(journal: Journal) -> JournalRead:
    return JournalRead(
        id=journal.id,
        application_id=journal.application_id,
        company_name=journal.application.company_name,
        position_title=journal.application.position_title,
        round_id=journal.round_id,
        round_name=journal.round.name if journal.round else None,
        template=journal.template,
        occurred_on=journal.occurred_on,
        responses=journal.responses,
        interviewer_feedback=journal.interviewer_feedback,
        user_interpretation=journal.user_interpretation,
        follow_up_actions=journal.follow_up_actions,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
        questions=[question_read(q) for q in journal.questions],
    )


@router.get("/journal-templates", response_model=list[TemplateRead])
def journal_templates() -> list[dict]:
    """The prompts for each kind of journal. Journals only accept answers to these prompts."""
    return [
        {
            "template": template,
            "label": meta["label"],
            "description": meta["description"],
            "prompts": [{"key": p.key, "question": p.question, "hint": p.hint} for p in meta["prompts"]],
        }
        for template, meta in TEMPLATES.items()
    ]


@router.get("/journals", response_model=list[JournalRead])
def list_journals(user: CurrentUser, db: DbSession, application_id: uuid.UUID | None = None) -> list[JournalRead]:
    return [journal_read(j) for j in service.list_journals(db, user, application_id)]


@router.post("/journals", response_model=JournalRead, status_code=status.HTTP_201_CREATED)
def create_journal(body: JournalCreate, user: CurrentUser, db: DbSession) -> JournalRead:
    """Records a journal, and any questions in it, which go into your question bank."""
    data = body.model_dump()
    return journal_read(service.create_journal(db, user, data))


@router.get("/journals/{journal_id}", response_model=JournalRead)
def get_journal(journal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JournalRead:
    return journal_read(service.get_journal(db, user, journal_id))


@router.patch("/journals/{journal_id}", response_model=JournalRead)
def update_journal(journal_id: uuid.UUID, body: JournalUpdate, user: CurrentUser, db: DbSession) -> JournalRead:
    return journal_read(service.update_journal(db, user, journal_id, body.changes()))


@router.post("/journals/{journal_id}/questions", response_model=JournalRead, status_code=status.HTTP_201_CREATED)
def add_questions(journal_id: uuid.UUID, body: list[QuestionFields], user: CurrentUser, db: DbSession) -> JournalRead:
    items = TypeAdapter(list[QuestionFields]).dump_python(body)
    return journal_read(service.add_questions(db, user, journal_id, items))


@router.delete("/journals/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal(journal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Deletes the journal. Its questions stay in your question bank."""
    service.delete_journal(db, user, journal_id)
