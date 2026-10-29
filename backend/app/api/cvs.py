import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app import storage
from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models import CVSection
from app.schemas.cv import CVVersionDetail, CVVersionSummary, CVVersionUpdate, SectionRead, SectionUpdate
from app.services import cvs as service

router = APIRouter(prefix="/cv-versions", tags=["cv"])


def _detail(db: DbSession, version) -> CVVersionDetail:
    detail = CVVersionDetail.model_validate(version)
    detail.application_count = service.application_count(db, version.id)
    return detail


@router.get("", response_model=list[CVVersionSummary])
def list_versions(user: CurrentUser, db: DbSession) -> list[CVVersionSummary]:
    summaries = []
    for version, count in service.list_versions(db, user):
        summary = CVVersionSummary.model_validate(version)
        summary.application_count = count
        summaries.append(summary)
    return summaries


@router.post("", response_model=CVVersionDetail, status_code=status.HTTP_201_CREATED)
def upload_cv(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="PDF or DOCX, up to 4 MB.")],
    label: Annotated[str | None, Form(max_length=100)] = None,
) -> CVVersionDetail:
    """Uploads a CV, keeps the original file, and extracts its sections.

    The file type is decided from its content, not its name. A readable file
    with no usable text is saved with `parse_status: failed` and a warning.
    """
    data = file.file.read(get_settings().cv_max_bytes + 1)  # one extra byte reveals "too large"
    version = service.upload_cv(db, user, file.filename, data, label.strip() if label else None)
    return _detail(db, version)


@router.get("/{version_id}", response_model=CVVersionDetail)
def get_version(version_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CVVersionDetail:
    return _detail(db, service.get_version(db, user, version_id))


@router.patch("/{version_id}", response_model=CVVersionDetail)
def update_version(version_id: uuid.UUID, body: CVVersionUpdate, user: CurrentUser, db: DbSession) -> CVVersionDetail:
    return _detail(db, service.update_version(db, user, version_id, body.changes()))


@router.patch("/{version_id}/sections/{section_id}", response_model=SectionRead)
def update_section(
    version_id: uuid.UUID, section_id: uuid.UUID, body: SectionUpdate, user: CurrentUser, db: DbSession
) -> CVSection:
    """Corrects the section type the parser chose."""
    return service.update_section(db, user, version_id, section_id, body.section_type)


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(version_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Deletes a CV version and its file. Refused while any application uses it."""
    service.delete_version(db, user, version_id)


@router.get("/{version_id}/file", response_class=Response)
def download_original(version_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """The original uploaded file, byte for byte, always as a download (never shown inline)."""
    document = service.get_version(db, user, version_id).document
    return Response(
        storage.read(document.storage_key),
        media_type=document.mime_type,
        headers={
            # RFC 5987 form, so any filename (spaces, non-ASCII) survives.
            "Content-Disposition": f"attachment; filename*=utf-8''{quote(document.original_filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
