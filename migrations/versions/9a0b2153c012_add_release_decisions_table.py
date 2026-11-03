"""add release decisions table

Revision ID: 9a0b2153c012
Revises: 13d6ff9f4f3c
Create Date: 2026-10-15 05:12:30.677286

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9a0b2153c012'
down_revision: str | Sequence[str] | None = '13d6ff9f4f3c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'release_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False),
        sa.Column('decision', sa.String(), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('policy_version', sa.String(), nullable=False),
        sa.Column('triggering_fact', sa.String(), nullable=False),
        sa.Column('evidence_reference', sa.String(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('origin', sa.String(), nullable=False),
        sa.Column('authorized_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.CheckConstraint("decision IN ('RELEASE', 'REFUND')", name='check_release_decision_type'),
        sa.CheckConstraint("origin IN ('AUTOMATIC', 'MANUAL')", name='check_release_decision_origin'),
        sa.CheckConstraint('amount_kobo > 0', name='check_release_decision_amount_positive'),
    )
    op.create_index('ix_release_decisions_fund_disposition_id', 'release_decisions', ['fund_disposition_id'])


def downgrade() -> None:
    op.drop_table('release_decisions')
