"""SQLAlchemy models.

Import every model module here so Alembic's autogenerate sees all tables
through `Base.metadata`.
"""

from app.models.base import Base

__all__ = ["Base"]
