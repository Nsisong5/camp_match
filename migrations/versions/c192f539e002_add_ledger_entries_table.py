"""add ledger entries table

Revision ID: c192f539e002
Revises: 9a0b2153c012
Create Date: 2026-10-15 06:45:08.928886

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c192f539e002'
down_revision: str | Sequence[str] | None = '9a0b2153c012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entry_type', sa.String(), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('reference_type', sa.String(), nullable=False),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('CHARGE', 'HOLD_ALLOCATION', 'RELEASE', 'REFUND', 'REVERSAL', 'CORRECTION')",
            name='check_ledger_entry_type',
        ),
    )
    op.create_index('ix_ledger_entries_payment_id', 'ledger_entries', ['payment_id'], postgresql_where=sa.text('payment_id IS NOT NULL'))
    op.create_index('ix_ledger_entries_fund_disposition_id', 'ledger_entries', ['fund_disposition_id'], postgresql_where=sa.text('fund_disposition_id IS NOT NULL'))
    op.create_index('ix_ledger_entries_entry_type', 'ledger_entries', ['entry_type'])


def downgrade() -> None:
    op.drop_table('ledger_entries')
