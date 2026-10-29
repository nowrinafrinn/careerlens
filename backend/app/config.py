"""Application settings, read from environment variables (and backend/.env in development)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Absolute path, so settings load the same whether you start from backend/ or the repo root.
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://careerlens:careerlens@localhost:5432/careerlens"
    test_database_url: str = "postgresql+psycopg://careerlens:careerlens@localhost:5432/careerlens_test"
    # Seconds to wait when opening a DB connection. Without it, an unreachable
    # database makes requests hang for ~2 minutes instead of failing fast.
    db_connect_timeout: int = 5

    # Auth
    session_ttl_days: int = 14
    # Send the session cookie over HTTPS only. Must be true in any deployment;
    # false locally because http://localhost has no TLS.
    cookie_secure: bool = False
    # Set false on a public deployment once your own account exists.
    allow_registration: bool = True

    # Uploaded files (original CVs). Never committed: see .gitignore.
    storage_dir: Path = BACKEND_DIR / "storage"
    cv_max_bytes: int = 5 * 1024 * 1024

    # Optional AI (Google Gemini). Without a key the app runs on the rule
    # engine only. The key stays on the server; the browser never sees it.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str | None = None  # only for a proxy or a local stand-in; normally unset
    ai_timeout_seconds: int = 60
    ai_max_attempts: int = 3  # rate limits and server errors are retried with backoff


@lru_cache
def get_settings() -> Settings:
    return Settings()
