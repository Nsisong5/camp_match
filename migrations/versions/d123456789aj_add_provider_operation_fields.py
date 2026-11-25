"""add provider operation fields to operations tables

Revision ID: d123456789aj
Revises: d123456789ai
Create Date: 2026-11-25 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'd123456789aj'
down_revision = 'd123456789ai'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('release_operations', sa.Column('provider_operation_id', sa.String(), nullable=True))
    op.add_column('release_operations', sa.Column('provider_fee_kobo', sa.BigInteger(), nullable=True))
    
    op.add_column('refund_operations', sa.Column('provider_operation_id', sa.String(), nullable=True))
    op.add_column('refund_operations', sa.Column('provider_fee_kobo', sa.BigInteger(), nullable=True))
    op.add_column('refund_operations', sa.Column('provider_status_detail', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('release_operations', 'provider_operation_id')
    op.drop_column('release_operations', 'provider_fee_kobo')
    
    op.drop_column('refund_operations', 'provider_operation_id')
    op.drop_column('refund_operations', 'provider_fee_kobo')
    op.drop_column('refund_operations', 'provider_status_detail')
