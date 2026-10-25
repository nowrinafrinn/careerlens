"""SQLAlchemy models.

Import every model module here so Alembic's autogenerate sees all tables
through `Base.metadata`.
"""

from app.models.analysis import CVRecommendation, JobRequirement, RequirementAnalysis, RequirementEvidence
from app.models.application import JobApplication, RecruitmentEvent, RecruitmentRound
from app.models.base import Base
from app.models.cv import CVDocument, CVPassage, CVSection, CVVersion
from app.models.journal import Journal, Question, QuestionAttempt
from app.models.learning import GapEvidence, GapReassessment, SkillGap, Task, TaskAttempt
from app.models.user import User, UserSession

__all__ = [
    "Base",
    "CVDocument",
    "CVPassage",
    "CVRecommendation",
    "CVSection",
    "CVVersion",
    "GapEvidence",
    "GapReassessment",
    "SkillGap",
    "Task",
    "TaskAttempt",
    "JobApplication",
    "JobRequirement",
    "Journal",
    "Question",
    "QuestionAttempt",
    "RecruitmentEvent",
    "RequirementAnalysis",
    "RequirementEvidence",
    "RecruitmentRound",
    "User",
    "UserSession",
]
