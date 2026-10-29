from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.ai.provider import AIProvider, get_ai_provider
from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.auth import UserRead

router = APIRouter(tags=["ai"])

# Shown on the consent screen, so it must stay true to what build_request sends.
DATA_SENT = (
    "When you choose “Analyse with AI”, the job description's requirement lines and the text of your CV's "
    "sections (not its top part with your name and contact details) are sent to {provider}. The rule-based "
    "analysis never sends anything. On free API plans the provider may use what it receives to improve its "
    "products, so don't use a real CV unless you're comfortable with that."
)


class AIStatus(BaseModel):
    available: bool  # a provider is configured on this server
    provider: str | None
    model: str | None
    consented: bool
    consent_given_at: datetime | None
    data_sent: str


class ConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: bool


@router.get("/ai/status", response_model=AIStatus)
def ai_status(user: CurrentUser, provider: Annotated[AIProvider | None, Depends(get_ai_provider)]) -> AIStatus:
    return AIStatus(
        available=provider is not None,
        provider=provider.name if provider else None,
        model=provider.model if provider else None,
        consented=user.ai_processing_consent_at is not None,
        consent_given_at=user.ai_processing_consent_at,
        data_sent=DATA_SENT.format(provider=provider.name if provider else "the AI provider"),
    )


@router.patch("/users/me/ai-consent", response_model=UserRead)
def set_ai_consent(body: ConsentUpdate, user: CurrentUser, db: DbSession) -> User:
    """Give or withdraw consent to send CV text to the AI provider. Withdrawing takes effect at once."""
    if body.consent and user.ai_processing_consent_at is None:
        user.ai_processing_consent_at = datetime.now(UTC)
    elif not body.consent:
        user.ai_processing_consent_at = None
    db.commit()
    return user
