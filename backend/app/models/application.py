import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import ApplicationStatus, EventType, RoundResult, RoundStatus, RoundType, db_enum


class JobApplication(UUIDPrimaryKey, Timestamps, Base):
    """One job the user is interested in or has applied to. Owned by exactly one user."""

    __tablename__ = "job_applications"
    __table_args__ = (Index("ix_job_applications_user_id_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_name: Mapped[str] = mapped_column(String(200))
    position_title: Mapped[str] = mapped_column(String(200))
    job_description: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(String(2048))
    source: Mapped[str | None] = mapped_column(String(100))  # "LinkedIn", "referral", ...
    deadline: Mapped[date | None] = mapped_column(Date)
    applied_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ApplicationStatus] = mapped_column(
        db_enum(ApplicationStatus, "application_status"), default=ApplicationStatus.INTERESTED
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # Soft archive: hidden from the default list, never deleted, history intact.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rounds: Mapped[list["RecruitmentRound"]] = relationship(
        back_populates="application",
        order_by="RecruitmentRound.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RecruitmentRound(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "recruitment_rounds"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)  # display order within the application
    name: Mapped[str] = mapped_column(String(200))
    round_type: Mapped[RoundType] = mapped_column(db_enum(RoundType, "round_type"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Status and result are deliberately separate: "completed" never implies "passed".
    status: Mapped[RoundStatus] = mapped_column(db_enum(RoundStatus, "round_status"))
    result: Mapped[RoundResult] = mapped_column(db_enum(RoundResult, "round_result"), default=RoundResult.UNKNOWN)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    links: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)  # [{"label", "url"}]
    notes: Mapped[str | None] = mapped_column(Text)

    application: Mapped[JobApplication] = relationship(back_populates="rounds")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RecruitmentEvent(UUIDPrimaryKey, Base):
    """Append-only history. Rows are inserted, never updated or deleted by the app.

    `old_value`/`new_value` hold the changed fields as JSON, so a reschedule
    keeps the original date even after the round itself has moved on.
    """

    __tablename__ = "recruitment_events"
    __table_args__ = (Index("ix_recruitment_events_application_id_occurred_at", "application_id", "occurred_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_applications.id", ondelete="CASCADE"))
    # SET NULL: deleting a round keeps its history (the snapshot is in old_value).
    round_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recruitment_rounds.id", ondelete="SET NULL"))
    event_type: Mapped[EventType] = mapped_column(db_enum(EventType, "event_type"))
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    # Set in Python (not now()), so several events in one transaction keep their real order.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
