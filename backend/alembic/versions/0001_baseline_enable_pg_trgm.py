"""baseline enable pg_trgm

The first migration creates no tables. It enables pg_trgm, which the question
bank uses later for fuzzy text search, and gives every later migration a
common starting point.

Revision ID: 0001
Revises: 
Create Date: 2026-10-25 16:38:14.386552

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
