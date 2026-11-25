"""add payout_accounts table

Revision ID: d123456789ak
Revises: d123456789aj
Create Date: 2026-11-25 01:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd123456789ak'
down_revision = 'd123456789aj'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payout_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scout_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('bank_code', sa.String(), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('status', sa.String(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('replaced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('release_hold_until', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE', 'REPLACED')", name="check_payout_account_status"),
    )
    op.create_index(
        'ix_payout_accounts_active_scout',
        'payout_accounts',
        ['scout_id'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'")
    )


def downgrade() -> None:
    op.drop_index('ix_payout_accounts_active_scout', table_name='payout_accounts')
    op.drop_table('payout_accounts')
