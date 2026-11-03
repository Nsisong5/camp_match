"""add university_id to student_profiles

Revision ID: 61f548d512a8
Revises: 319ed2f3f680
Create Date: 2026-10-09 18:49:33.846087

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '61f548d512a8'
down_revision: str | Sequence[str] | None = '319ed2f3f680'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('student_profiles', sa.Column('university_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_student_profiles_university_id'), 'student_profiles', ['university_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_student_profiles_university_id'), table_name='student_profiles')
    op.drop_column('student_profiles', 'university_id')
