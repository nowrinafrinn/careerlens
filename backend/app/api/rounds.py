import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import RecruitmentRound
from app.schemas.rounds import RoundRead, RoundUpdate
from app.services import rounds as service

router = APIRouter(prefix="/rounds", tags=["rounds"])


@router.get("/{round_id}", response_model=RoundRead)
def get_round(round_id: uuid.UUID, user: CurrentUser, db: DbSession) -> RecruitmentRound:
    return service.get_round(db, user, round_id)


@router.patch("/{round_id}", response_model=RoundRead)
def update_round(round_id: uuid.UUID, body: RoundUpdate, user: CurrentUser, db: DbSession) -> RecruitmentRound:
    """Partial update. Changing `scheduled_at` records a reschedule that keeps the old date."""
    return service.update_round(db, user, round_id, body.changes(exclude={"change_reason"}), reason=body.change_reason)


@router.delete("/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_round(
    round_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    reason: Annotated[str | None, Query(max_length=1000)] = None,
) -> None:
    """Deletes a round created by mistake. Its history is kept, with a snapshot of the round."""
    service.delete_round(db, user, round_id, reason=reason)
