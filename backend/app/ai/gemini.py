"""Google Gemini, via the official google-genai SDK.

Asks for JSON that follows a schema, at temperature 0. Rate limits (429) and
server errors (5xx) are retried with exponential backoff; anything else, or
running out of attempts, raises AIProviderError with a short reason.
"""

import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.ai.provider import AIProviderError

_RETRYABLE = {429, 500, 502, 503, 504}


class GeminiProvider:
    name = "Google Gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: int = 60,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        client: Any = None,
    ):
        self.model = model
        self._max_attempts = max(1, max_attempts)
        self._sleep = sleep
        # The SDK takes its timeout in milliseconds. Our own loop does the retrying.
        self._client = client or genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000, base_url=base_url)
        )

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
            except errors.APIError as exc:
                if exc.code in _RETRYABLE and attempt < self._max_attempts:
                    self._sleep(2 ** (attempt - 1))  # 1 s, 2 s, 4 s…
                    continue
                if exc.code == 429:
                    raise AIProviderError("The AI service's rate limit was reached. Try again in a minute.") from exc
                if exc.code in (401, 403):
                    raise AIProviderError("The AI service rejected the API key.") from exc
                raise AIProviderError(f"The AI service returned an error ({exc.code}).") from exc
            except httpx.TimeoutException as exc:
                if attempt < self._max_attempts:
                    self._sleep(2 ** (attempt - 1))
                    continue
                raise AIProviderError("The AI service didn't answer in time.") from exc
            text = response.text
            if not text:
                raise AIProviderError("The AI service returned an empty answer.")
            return text
        raise AIProviderError("The AI service couldn't be reached.")  # pragma: no cover (loop always returns or raises)
