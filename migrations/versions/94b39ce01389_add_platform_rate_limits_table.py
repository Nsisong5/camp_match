"""add platform rate limits table

Revision ID: 94b39ce01389
Revises: d123456789af
Create Date: 2026-11-09 22:28:43.466709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94b39ce01389'
down_revision: Union[str, Sequence[str], None] = 'd123456789af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'platform_rate_limits',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.PrimaryKeyConstraint('key', 'window_start', name='pk_platform_rate_limits')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('platform_rate_limits')
