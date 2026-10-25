import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.analysis.cv_parser import ParseStatus, SectionType
from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import db_enum


class CVDocument(UUIDPrimaryKey, Base):
    """The uploaded file exactly as received. Never modified; the bytes live on disk."""

    __tablename__ = "cv_documents"
    __table_args__ = (UniqueConstraint("user_id", "sha256", name="uq_cv_documents_user_id_sha256"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(300))  # path relative to the storage directory
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CVVersion(UUIDPrimaryKey, Timestamps, Base):
    """The parsed, user-correctable reading of one uploaded document.

    Applications point at a version, so different applications can use
    different CVs, and one version can serve many applications.
    """

    __tablename__ = "cv_versions"
    __table_args__ = (UniqueConstraint("user_id", "version_number", name="uq_cv_versions_user_id_version_number"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cv_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_documents.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100))
    # The normalised extracted text. Every section/passage offset points into it.
    raw_text: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[ParseStatus] = mapped_column(db_enum(ParseStatus, "parse_status"))
    parse_warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[CVDocument] = relationship()
    sections: Mapped[list["CVSection"]] = relationship(
        back_populates="cv_version", order_by="CVSection.position", cascade="all, delete-orphan", passive_deletes=True
    )

    # Read-through properties so API schemas can describe the file alongside the version.
    @property
    def original_filename(self) -> str:
        return self.document.original_filename

    @property
    def mime_type(self) -> str:
        return self.document.mime_type

    @property
    def size_bytes(self) -> int:
        return self.document.size_bytes


class CVSection(UUIDPrimaryKey, Base):
    __tablename__ = "cv_sections"
    __table_args__ = (CheckConstraint("char_start >= 0 AND char_end >= char_start", name="offsets"),)

    cv_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_versions.id", ondelete="CASCADE"), index=True)
    section_type: Mapped[SectionType] = mapped_column(db_enum(SectionType, "section_type"))
    heading_text: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    # The section type was set by the user, not the parser.
    user_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    cv_version: Mapped[CVVersion] = relationship(back_populates="sections")
    passages: Mapped[list["CVPassage"]] = relationship(
        back_populates="section", order_by="CVPassage.position", cascade="all, delete-orphan", passive_deletes=True
    )


class CVPassage(UUIDPrimaryKey, Base):
    """One bullet or line of the CV. Requirement evidence (next milestone) points here."""

    __tablename__ = "cv_passages"
    __table_args__ = (CheckConstraint("char_start >= 0 AND char_end > char_start", name="offsets"),)

    cv_section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_sections.id", ondelete="CASCADE"), index=True)
    cv_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cv_versions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)

    section: Mapped[CVSection] = relationship(back_populates="passages")
    # Direct link too, so evidence queries can find a version's passages without going through sections.
    cv_version: Mapped[CVVersion] = relationship()
