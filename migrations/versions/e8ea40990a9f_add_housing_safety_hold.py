"""add housing safety hold

Revision ID: e8ea40990a9f
Revises: 64029e21ee39
Create Date: 2026-10-19 21:00:00.000000

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = 'e8ea40990a9f'
down_revision: str | Sequence[str] | None = '64029e21ee39'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('suspension_reference', sa.Uuid(), nullable=True))
    op.drop_constraint('check_listing_status', 'listings', type_='check')
    op.create_check_constraint(
        'check_listing_status',
        'listings',
        "status IN ('DRAFT', 'PUBLISHED', 'UNAVAILABLE', 'ARCHIVED', 'SUSPENDED')"
    )


def downgrade() -> None:
    op.drop_constraint('check_listing_status', 'listings', type_='check')
    op.create_check_constraint(
        'check_listing_status',
        'listings',
        "status IN ('DRAFT', 'PUBLISHED', 'UNAVAILABLE', 'ARCHIVED')"
    )
    op.drop_column('listings', 'suspension_reference')
