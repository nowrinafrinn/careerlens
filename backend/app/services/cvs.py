"""CV upload, review and correction.

The uploaded file is stored untouched; everything the parser derived from it
(text, sections, passages) lives in the database and can be corrected.
"""

import hashlib
import uuid
from pathlib import PurePath
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import storage
from app.analysis.cv_parser import MIME_TYPES, SectionType, UnsupportedFile, parse_cv
from app.config import get_settings
from app.errors import AppError
from app.models import CVDocument, CVPassage, CVSection, CVVersion, JobApplication, User


def _not_found() -> AppError:
    return AppError(404, "not_found", "CV version not found.")


def _display_filename(filename: str | None) -> str:
    # Only the last path component, trimmed; it's shown back to the user, never used as a path.
    name = PurePath((filename or "").replace("\\", "/")).name.strip()
    return (name or "cv")[:255]


def get_version(db: Session, user: User, version_id: uuid.UUID) -> CVVersion:
    version = db.scalar(select(CVVersion).where(CVVersion.id == version_id, CVVersion.user_id == user.id))
    if version is None:
        raise _not_found()
    return version


def application_count(db: Session, version_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(JobApplication.cv_version_id == version_id)) or 0


def list_versions(db: Session, user: User) -> list[tuple[CVVersion, int]]:
    counts = (
        select(JobApplication.cv_version_id, func.count().label("n"))
        .group_by(JobApplication.cv_version_id)
        .subquery()
    )
    rows = db.execute(
        select(CVVersion, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.cv_version_id == CVVersion.id)
        .where(CVVersion.user_id == user.id)
        .order_by(CVVersion.version_number.desc())
    ).all()
    return [(version, count) for version, count in rows]


def upload_cv(db: Session, user: User, filename: str | None, data: bytes, label: str | None) -> CVVersion:
    if not data:
        raise AppError(422, "empty_file", "The file is empty.")
    if len(data) > get_settings().cv_max_bytes:
        raise AppError(413, "file_too_large", "The file is larger than the 5 MB limit.")
    try:
        kind, parsed = parse_cv(data)
    except UnsupportedFile as error:
        raise AppError(415, "unsupported_file", str(error)) from None

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(CVVersion)
        .join(CVDocument, CVVersion.cv_document_id == CVDocument.id)
        .where(CVDocument.user_id == user.id, CVDocument.sha256 == digest)
    )
    if existing is not None:
        raise AppError(
            409,
            "duplicate_cv",
            f"You already uploaded this exact file as “{existing.label}”.",
            {"cv_version_id": str(existing.id)},
        )

    display_name = _display_filename(filename)
    version_number = (db.scalar(select(func.max(CVVersion.version_number)).where(CVVersion.user_id == user.id)) or 0) + 1
    key = storage.new_key("cvs", user.id, kind.value)
    storage.save(key, data)

    try:
        document = CVDocument(
            user_id=user.id,
            original_filename=display_name,
            mime_type=MIME_TYPES[kind],
            size_bytes=len(data),
            sha256=digest,
            storage_key=key,
        )
        version = CVVersion(
            user_id=user.id,
            document=document,
            version_number=version_number,
            label=(label or PurePath(display_name).stem or f"CV {version_number}")[:100],
            raw_text=parsed.text,
            parse_status=parsed.status,
            parse_warnings=parsed.warnings,
            is_confirmed=False,
        )
        for s_index, section in enumerate(parsed.sections):
            row = CVSection(
                section_type=section.section_type,
                heading_text=section.heading[:200] if section.heading else None,
                position=s_index,
                char_start=section.char_start,
                char_end=section.char_end,
            )
            row.passages = [
                CVPassage(
                    cv_version=version,
                    text=passage.text,
                    position=p_index,
                    char_start=passage.char_start,
                    char_end=passage.char_end,
                )
                for p_index, passage in enumerate(section.passages)
            ]
            version.sections.append(row)
        db.add(version)
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(key)
        # Same file uploaded twice at the same moment, or a version-number race.
        raise AppError(409, "duplicate_cv", "This upload conflicted with another one. Refresh and try again.") from None
    except Exception:
        db.rollback()
        storage.delete(key)  # never leave an orphaned file behind
        raise
    return version


def update_version(db: Session, user: User, version_id: uuid.UUID, changes: dict[str, Any]) -> CVVersion:
    version = get_version(db, user, version_id)
    for field, value in changes.items():
        setattr(version, field, value)
    db.commit()
    return version


def update_section(
    db: Session, user: User, version_id: uuid.UUID, section_id: uuid.UUID, section_type: SectionType
) -> CVSection:
    version = get_version(db, user, version_id)
    section = next((s for s in version.sections if s.id == section_id), None)
    if section is None:
        raise AppError(404, "not_found", "Section not found.")
    if section.section_type != section_type:
        section.section_type = section_type
        section.user_corrected = True
    db.commit()
    return section


def delete_version(db: Session, user: User, version_id: uuid.UUID) -> None:
    version = get_version(db, user, version_id)
    in_use = application_count(db, version.id)
    if in_use:
        raise AppError(
            409,
            "cv_in_use",
            f"This CV is linked to {in_use} application{'s' if in_use != 1 else ''}. "
            "Choose a different CV for them first.",
        )
    document = version.document
    db.delete(version)
    db.flush()
    db.delete(document)
    db.commit()
    storage.delete(document.storage_key)  # after the commit: a failed commit keeps the file


def ensure_owned(db: Session, user: User, version_id: uuid.UUID | None) -> None:
    """For linking an application to a CV: the version must belong to the same user."""
    if version_id is not None:
        get_version(db, user, version_id)
