"""SQLAlchemy models.

Import every model module here so Alembic's autogenerate sees all tables
through `Base.metadata`.
"""

from app.models.application import JobApplication, RecruitmentEvent, RecruitmentRound
from app.models.base import Base
from app.models.user import User, UserSession

__all__ = ["Base", "JobApplication", "RecruitmentEvent", "RecruitmentRound", "User", "UserSession"]
