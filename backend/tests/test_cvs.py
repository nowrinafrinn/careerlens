from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.conftest import act_as, sign_up
from tests.cv_files import SAMPLE_CV_LINES, make_docx, make_pdf

API = "/api/v1/cv-versions"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def upload(client: TestClient, data: bytes, filename: str = "Rafi_CV.pdf", mime: str = PDF_MIME, label: str | None = None):
    form = {"label": label} if label else None
    return client.post(API, files={"file": (filename, data, mime)}, data=form)


def stored_files(storage_dir: Path) -> list[Path]:
    return [p for p in storage_dir.rglob("*") if p.is_file()] if storage_dir.exists() else []


# --- upload and extraction -------------------------------------------------------------


def test_upload_pdf_extracts_sections_and_keeps_the_original(ada: TestClient, storage_dir: Path) -> None:
    original = make_pdf(SAMPLE_CV_LINES)

    response = upload(ada, original)

    assert response.status_code == 201, response.text
    cv = response.json()
    assert cv["version_number"] == 1
    assert cv["label"] == "Rafi_CV"  # from the file name when no label is given
    assert cv["original_filename"] == "Rafi_CV.pdf"
    assert cv["mime_type"] == PDF_MIME
    assert cv["parse_status"] == "ok"
    assert cv["is_confirmed"] is False
    assert [s["section_type"] for s in cv["sections"]] == [
        "header", "summary", "education", "skills", "experience", "projects",
    ]
    for section in cv["sections"]:
        for passage in section["passages"]:
            assert cv["raw_text"][passage["char_start"] : passage["char_end"]] == passage["text"]

    # The stored file is byte-for-byte the upload.
    assert [p.read_bytes() for p in stored_files(storage_dir)] == [original]
    download = ada.get(f"{API}/{cv['id']}/file")
    assert download.status_code == 200
    assert download.content == original
    assert download.headers["content-type"] == PDF_MIME
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["x-content-type-options"] == "nosniff"


def test_upload_docx_with_label(ada: TestClient) -> None:
    data = make_docx([("Education", "Heading 1"), ("BSc Computer Science", None), ("Skills", "Heading 1"), ("Python, SQL, Docker and Git", None)])

    response = upload(ada, data, "cv.docx", DOCX_MIME, label="  Backend CV  ")

    assert response.status_code == 201, response.text
    assert response.json()["label"] == "Backend CV"
    assert response.json()["mime_type"] == DOCX_MIME


def test_file_type_comes_from_content_not_name_or_header(ada: TestClient, storage_dir: Path) -> None:
    response = upload(ada, b"This is plain text renamed to look like a PDF.", "cv.pdf", PDF_MIME)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file"
    assert stored_files(storage_dir) == []
    assert ada.get(API).json() == []


def test_docx_named_as_pdf_is_still_read_as_docx(ada: TestClient) -> None:
    data = make_docx([("Experience", "Heading 1"), ("Backend intern working with Python services.", None)])

    response = upload(ada, data, "cv.pdf", PDF_MIME)

    assert response.status_code == 201
    assert response.json()["mime_type"] == DOCX_MIME


def test_empty_file_is_rejected(ada: TestClient) -> None:
    response = upload(ada, b"")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"


def test_file_over_the_limit_is_rejected_before_reading(ada: TestClient, storage_dir: Path) -> None:
    too_big = b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024)

    response = upload(ada, too_big)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert stored_files(storage_dir) == []


def test_size_is_checked_again_after_reading(ada: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The early check trusts Content-Length; the route measures the real bytes too.
    monkeypatch.setattr(get_settings(), "cv_max_bytes", 1000)

    response = upload(ada, make_pdf(SAMPLE_CV_LINES))

    assert response.status_code == 413


def test_pdf_without_text_is_saved_as_failed_with_explanation(ada: TestClient) -> None:
    response = upload(ada, make_pdf([]), "scan.pdf")

    assert response.status_code == 201
    cv = response.json()
    assert cv["parse_status"] == "failed"
    assert "scanned image" in cv["parse_warnings"][0]


def test_same_file_twice_is_reported_not_duplicated(ada: TestClient) -> None:
    data = make_pdf(SAMPLE_CV_LINES)
    first = upload(ada, data).json()

    second = upload(ada, data, "renamed.pdf")

    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "duplicate_cv"
    assert error["details"]["cv_version_id"] == first["id"]


def test_versions_are_numbered_and_listed_newest_first(ada: TestClient) -> None:
    upload(ada, make_pdf(SAMPLE_CV_LINES), "one.pdf")
    upload(ada, make_pdf([*SAMPLE_CV_LINES, "Achievements", "Hackathon finalist 2024"]), "two.pdf")

    listed = ada.get(API).json()

    assert [(v["version_number"], v["label"]) for v in listed] == [(2, "two"), (1, "one")]
    assert "sections" not in listed[0]  # the list is a summary


def test_file_name_is_reduced_to_its_last_part(ada: TestClient) -> None:
    response = upload(ada, make_pdf(SAMPLE_CV_LINES), "..\\..\\secret\\evil.pdf")

    assert response.json()["original_filename"] == "evil.pdf"


# --- corrections ---------------------------------------------------------------------


def test_section_type_can_be_corrected(ada: TestClient) -> None:
    cv = upload(ada, make_docx([("Open Source", "Heading 1"), ("Contributed fixes to a Python library.", None)]), "cv.docx", DOCX_MIME).json()
    section = next(s for s in cv["sections"] if s["section_type"] == "unrecognized")

    response = ada.patch(f"{API}/{cv['id']}/sections/{section['id']}", json={"section_type": "other_experience"})

    assert response.status_code == 200
    assert response.json()["section_type"] == "other_experience"
    assert response.json()["user_corrected"] is True
    reloaded = ada.get(f"{API}/{cv['id']}").json()
    assert next(s for s in reloaded["sections"] if s["id"] == section["id"])["user_corrected"] is True


def test_invalid_section_type_is_rejected(ada: TestClient) -> None:
    cv = upload(ada, make_pdf(SAMPLE_CV_LINES)).json()
    section_id = cv["sections"][0]["id"]

    response = ada.patch(f"{API}/{cv['id']}/sections/{section_id}", json={"section_type": "hobbies"})

    assert response.status_code == 422


def test_version_can_be_renamed_and_confirmed(ada: TestClient) -> None:
    cv = upload(ada, make_pdf(SAMPLE_CV_LINES)).json()

    response = ada.patch(f"{API}/{cv['id']}", json={"label": "Backend CV, Oct 2026", "is_confirmed": True})

    assert response.status_code == 200
    assert (response.json()["label"], response.json()["is_confirmed"]) == ("Backend CV, Oct 2026", True)


# --- link to applications --------------------------------------------------------------


def new_application(client: TestClient, **fields) -> dict:
    response = client.post("/api/v1/applications", json={"company_name": "Acme", "position_title": "Engineer", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_application_uses_a_cv_version_and_records_changes(ada: TestClient) -> None:
    first = upload(ada, make_pdf(SAMPLE_CV_LINES), "general.pdf").json()
    second = upload(ada, make_pdf([*SAMPLE_CV_LINES, "Certifications", "AWS Cloud Practitioner"]), "backend.pdf").json()
    app = new_application(ada, cv_version_id=first["id"])
    assert app["cv_version"]["label"] == "general"

    updated = ada.patch(f"/api/v1/applications/{app['id']}", json={"cv_version_id": second["id"], "change_reason": "Tailored CV"})

    assert updated.json()["cv_version"]["id"] == second["id"]
    event = ada.get(f"/api/v1/applications/{app['id']}/timeline").json()[-1]
    assert event["event_type"] == "application_cv_changed"
    assert event["old_value"]["cv_label"] == "general"
    assert event["new_value"]["cv_label"] == "backend"
    assert event["reason"] == "Tailored CV"


def test_one_cv_version_can_serve_many_applications(ada: TestClient) -> None:
    cv = upload(ada, make_pdf(SAMPLE_CV_LINES)).json()
    new_application(ada, cv_version_id=cv["id"])
    new_application(ada, cv_version_id=cv["id"], company_name="Globex")

    assert ada.get(API).json()[0]["application_count"] == 2


def test_cv_in_use_cannot_be_deleted_until_unlinked(ada: TestClient, storage_dir: Path) -> None:
    cv = upload(ada, make_pdf(SAMPLE_CV_LINES)).json()
    app = new_application(ada, cv_version_id=cv["id"])

    blocked = ada.delete(f"{API}/{cv['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "cv_in_use"
    assert len(stored_files(storage_dir)) == 1

    ada.patch(f"/api/v1/applications/{app['id']}", json={"cv_version_id": None})
    assert ada.delete(f"{API}/{cv['id']}").status_code == 204
    assert ada.get(f"{API}/{cv['id']}").status_code == 404
    assert stored_files(storage_dir) == []


# --- isolation -------------------------------------------------------------------------


def test_other_users_cannot_see_use_or_change_a_cv(client: TestClient) -> None:
    ada_token = sign_up(client, "ada@example.com")
    cv = upload(client, make_pdf(SAMPLE_CV_LINES)).json()
    section_id = cv["sections"][0]["id"]
    sign_up(client, "grace@example.com")

    url = f"{API}/{cv['id']}"
    assert client.get(API).json() == []
    assert client.get(url).status_code == 404
    assert client.get(f"{url}/file").status_code == 404
    assert client.patch(url, json={"label": "mine now"}).status_code == 404
    assert client.patch(f"{url}/sections/{section_id}", json={"section_type": "skills"}).status_code == 404
    assert client.delete(url).status_code == 404
    # Nor attach it to their own application.
    response = client.post(
        "/api/v1/applications", json={"company_name": "Acme", "position_title": "Engineer", "cv_version_id": cv["id"]}
    )
    assert response.status_code == 404

    act_as(client, ada_token)
    assert client.get(url).json()["label"] == "Rafi_CV"


def test_same_file_can_be_uploaded_by_two_different_users(client: TestClient) -> None:
    data = make_pdf(SAMPLE_CV_LINES)
    sign_up(client, "ada@example.com")
    assert upload(client, data).status_code == 201
    sign_up(client, "grace@example.com")

    assert upload(client, data).status_code == 201  # duplicates are per user
