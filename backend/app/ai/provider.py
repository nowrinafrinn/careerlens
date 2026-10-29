"""The interface every AI provider implements, and how the app gets one."""

from typing import Any, Protocol

from app.config import get_settings


class AIProviderError(Exception):
    """The provider couldn't produce an answer (after its own retries).

    `reason` is a short, user-safe explanation; it never contains the prompt,
    the CV, or the API key.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class AIProvider(Protocol):
    name: str  # shown to the user, e.g. "Google Gemini"
    model: str

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        """Returns the model's raw JSON text for `schema`. Raises AIProviderError."""
        ...


def get_ai_provider() -> AIProvider | None:
    """The configured provider, or None when no API key is set.

    A FastAPI dependency, so tests swap in a fake provider.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    from app.ai.gemini import GeminiProvider  # the SDK is only imported when it's used

    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        max_attempts=settings.ai_max_attempts,
    )
