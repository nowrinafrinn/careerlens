import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.models import CVRecommendation
from app.models.analysis import RecommendationStatus
from app.schemas.recommendations import RecommendationDecision, RecommendationRead
from app.services import analyses as analyses_service
from app.services import recommendations as service

router = APIRouter(tags=["recommendations"])


def _read(rec: CVRecommendation) -> RecommendationRead:
    fields = {
        name: getattr(rec, name)
        for name in RecommendationRead.model_fields
        if name not in {"requirement_text", "number_warnings"}
    }
    return RecommendationRead(
        **fields, requirement_text=rec.requirement.text, number_warnings=service.number_warnings(rec)
    )


@router.get("/analyses/{analysis_id}/recommendations", response_model=list[RecommendationRead])
def list_recommendations(analysis_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[RecommendationRead]:
    """Suggested CV changes from this analysis. Your uploaded CV is never modified."""
    analysis = analyses_service.get_analysis(db, user, analysis_id)
    return [_read(rec) for rec in analysis.recommendations]


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationRead)
def decide(recommendation_id: uuid.UUID, body: RecommendationDecision, user: CurrentUser, db: DbSession) -> RecommendationRead:
    """Accept, edit (with your own `final_text`), reject, or undo (`proposed`) a suggestion."""
    rec = service.decide(db, user, recommendation_id, {"status": RecommendationStatus(body.status), "final_text": body.final_text})
    return _read(rec)
