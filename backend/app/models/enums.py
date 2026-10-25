"""Allowed values for status-like columns.

Stored as VARCHAR + CHECK constraint (not native Postgres enums), so adding a
value later is a small migration instead of an ALTER TYPE dance.
"""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def db_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,  # becomes the CHECK constraint name
        native_enum=False,
        create_constraint=True,
        length=40,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )


class ApplicationStatus(StrEnum):
    INTERESTED = "interested"
    PREPARING = "preparing"
    APPLIED = "applied"
    IN_PROGRESS = "in_progress"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED_UNKNOWN = "closed_unknown"


class RoundType(StrEnum):
    CV_SCREENING = "cv_screening"
    ONLINE_ASSESSMENT = "online_assessment"
    WRITTEN_EXAM = "written_exam"
    TECHNICAL_INTERVIEW = "technical_interview"
    HR_INTERVIEW = "hr_interview"
    MANAGERIAL_INTERVIEW = "managerial_interview"
    FINAL_DECISION = "final_decision"
    OTHER = "other"


class RoundStatus(StrEnum):
    """Where the round is in time. Says nothing about how it went: see RoundResult."""

    NOT_SCHEDULED = "not_scheduled"
    UPCOMING = "upcoming"
    PREPARING = "preparing"
    COMPLETED = "completed"
    AWAITING_RESULT = "awaiting_result"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class RoundResult(StrEnum):
    UNKNOWN = "unknown"
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class EventType(StrEnum):
    APPLICATION_CREATED = "application_created"
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    APPLICATION_DATE_CHANGED = "application_date_changed"
    APPLICATION_ARCHIVED = "application_archived"
    APPLICATION_RESTORED = "application_restored"
    APPLICATION_CV_CHANGED = "application_cv_changed"
    ROUND_CREATED = "round_created"
    ROUND_SCHEDULED = "round_scheduled"
    ROUND_RESCHEDULED = "round_rescheduled"
    ROUND_DATE_CHANGED = "round_date_changed"
    ROUND_STATUS_CHANGED = "round_status_changed"
    ROUND_RESULT_RECORDED = "round_result_recorded"
    ROUND_DELETED = "round_deleted"
