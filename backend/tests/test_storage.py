"""The Supabase Storage backend, with the HTTP layer faked (no network)."""

import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import get_settings
from app.errors import AppError
from tests.cv_files import SAMPLE_CV_LINES, make_pdf


class FakeSupabase:
    """Stands in for httpx.request: an in-memory bucket that records every call."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.fail_with: int | Exception | None = None

    def __call__(self, method: str, url: str, *, headers: dict, timeout: float, content: bytes | None = None) -> httpx.Response:
        self.calls.append((method, url, headers))
        request = httpx.Request(method, url)
        if isinstance(self.fail_with, Exception):
            raise self.fail_with
        if isinstance(self.fail_with, int):
            return httpx.Response(self.fail_with, request=request)
        key = url.split("/storage/v1/object/cv-files/", 1)[1]
        if method == "POST":
            if key in self.objects:
                return httpx.Response(409, request=request)
            self.objects[key] = content or b""
            return httpx.Response(200, json={"Key": key}, request=request)
        if method == "GET":
            if key not in self.objects:
                return httpx.Response(404, request=request)
            return httpx.Response(200, content=self.objects[key], request=request)
        if method == "DELETE":
            return httpx.Response(200 if self.objects.pop(key, None) is not None else 404, request=request)
        raise AssertionError(method)


@pytest.fixture
def supabase(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://demo.supabase.co/")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-key")
    fake = FakeSupabase()
    monkeypatch.setattr(httpx, "request", fake)
    return fake


def test_files_round_trip_through_a_private_bucket(supabase: FakeSupabase) -> None:
    key = storage.new_key("cvs", uuid.uuid4(), "pdf")

    storage.save(key, b"%PDF-1.4 data", "application/pdf")
    assert storage.read(key) == b"%PDF-1.4 data"
    storage.delete(key)
    storage.delete(key)  # deleting twice is fine

    method, url, headers = supabase.calls[0]
    assert (method, url) == ("POST", f"https://demo.supabase.co/storage/v1/object/cv-files/{key}")
    assert headers["Authorization"] == "Bearer service-key" and headers["apikey"] == "service-key"
    assert headers["Content-Type"] == "application/pdf" and headers["x-upsert"] == "false"
    assert supabase.objects == {}


def test_new_style_secret_keys_are_not_sent_as_bearer_tokens(supabase: FakeSupabase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", "sb_secret_abc123")

    storage.save("cvs/x/y.pdf", b"data")

    headers = supabase.calls[0][2]
    assert headers["apikey"] == "sb_secret_abc123" and "Authorization" not in headers


@pytest.mark.parametrize("failure", [500, httpx.ConnectError("down")])
def test_storage_failures_become_a_clear_503(supabase: FakeSupabase, failure) -> None:
    supabase.fail_with = failure

    with pytest.raises(AppError) as error:
        storage.save("cvs/x/y.pdf", b"data")

    assert (error.value.status_code, error.value.code) == (503, "storage_unavailable")


def test_missing_configuration_is_reported_not_crashed(supabase: FakeSupabase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "supabase_service_role_key", None)

    with pytest.raises(AppError, match="isn't configured"):
        storage.read("cvs/x/y.pdf")
    assert supabase.calls == []


def test_upload_and_download_through_the_api_use_the_bucket(ada: TestClient, supabase: FakeSupabase) -> None:
    original = make_pdf(SAMPLE_CV_LINES)

    cv = ada.post("/api/v1/cv-versions", files={"file": ("my cv.pdf", original, "application/pdf")}).json()
    download = ada.get(f"/api/v1/cv-versions/{cv['id']}/file")

    assert list(supabase.objects.values()) == [original]
    assert download.content == original
    assert download.headers["content-disposition"] == "attachment; filename*=utf-8''my%20cv.pdf"
