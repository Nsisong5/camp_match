"""add avatar_media_id to profiles

Revision ID: 78298898a964
Revises: 9f52f820d6d7
Create Date: 2026-09-24 22:10:20.100520

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '78298898a964'
down_revision: str | Sequence[str] | None = '9f52f820d6d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('profiles', sa.Column('avatar_media_id', sa.UUID(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('profiles', 'avatar_media_id')
