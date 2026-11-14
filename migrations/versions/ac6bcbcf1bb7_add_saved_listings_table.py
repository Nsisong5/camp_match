"""add saved_listings table

Revision ID: ac6bcbcf1bb7
Revises: 94b39ce01389
Create Date: 2026-11-10 07:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac6bcbcf1bb7'
down_revision: Union[str, Sequence[str], None] = '94b39ce01389'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'saved_listings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('saved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'listing_id', name='uq_saved_listings_user_listing')
    )
    op.create_index(op.f('ix_saved_listings_listing_id'), 'saved_listings', ['listing_id'], unique=False)
    op.create_index(op.f('ix_saved_listings_user_id'), 'saved_listings', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_saved_listings_user_id'), table_name='saved_listings')
    op.drop_index(op.f('ix_saved_listings_listing_id'), table_name='saved_listings')
    op.drop_table('saved_listings')
