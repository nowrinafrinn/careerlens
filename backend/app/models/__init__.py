"""SQLAlchemy models.

Import every model module here so Alembic's autogenerate sees all tables
through `Base.metadata`.
"""

from app.models.analysis import JobRequirement, RequirementAnalysis, RequirementEvidence
from app.models.application import JobApplication, RecruitmentEvent, RecruitmentRound
from app.models.base import Base
from app.models.cv import CVDocument, CVPassage, CVSection, CVVersion
from app.models.user import User, UserSession

__all__ = [
    "Base",
    "CVDocument",
    "CVPassage",
    "CVSection",
    "CVVersion",
    "JobApplication",
    "JobRequirement",
    "RecruitmentEvent",
    "RequirementAnalysis",
    "RequirementEvidence",
    "RecruitmentRound",
    "User",
    "UserSession",
]
