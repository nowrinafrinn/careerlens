"""ai assessment notes

Who judged each requirement's CV evidence (rule engine or AI), and plain notes
on how an analysis was made (e.g. why the AI was skipped).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29 15:05:17.217467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Plain VARCHAR plus an explicit CHECK, named like every other enum check
    # (add_column doesn't reliably create an Enum's constraint by itself).
    op.add_column('job_requirements', sa.Column('assessed_by', sa.String(length=40), server_default='rule_engine', nullable=False))
    op.create_check_constraint(
        op.f('ck_job_requirements_assessed_by'), 'job_requirements', "assessed_by IN ('rule_engine', 'ai')"
    )
    op.add_column('requirement_analyses', sa.Column('notes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('requirement_analyses', 'notes')
    op.drop_constraint(op.f('ck_job_requirements_assessed_by'), 'job_requirements', type_='check')
    op.drop_column('job_requirements', 'assessed_by')
