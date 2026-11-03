"""add payment core tables

Revision ID: 3f03100cd4d4
Revises: 81b3d0ddc9eb
Create Date: 2026-10-15 03:17:45.884564

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3f03100cd4d4'
down_revision: str | Sequence[str] | None = '81b3d0ddc9eb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. payment_attempts
    op.create_table(
        'payment_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('provider_reference', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount_kobo > 0', name='check_payment_attempt_amount_positive'),
        sa.CheckConstraint(
            "status IN ('INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'EXPIRED', 'CANCELLED')",
            name='check_payment_attempt_status',
        ),
        sa.UniqueConstraint('student_id', 'idempotency_key', name='uq_payment_attempt_student_idempotency'),
    )
    op.create_index('ix_payment_attempts_status', 'payment_attempts', ['status'])
    op.create_index('ix_payment_attempts_provider_reference', 'payment_attempts', ['provider_reference'], postgresql_where=sa.text('provider_reference IS NOT NULL'))

    # 2. payments
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_attempt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_attempts.id'), nullable=False, unique=True),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('provider_reference', sa.String(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount_kobo > 0', name='check_payment_amount_positive'),
    )

    # 3. fund_dispositions
    op.create_table(
        'fund_dispositions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payments.id'), nullable=False, unique=True),
        sa.Column('held_amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('held_amount_kobo > 0', name='check_fund_disposition_held_positive'),
        sa.CheckConstraint(
            "status IN ('HELD', 'DISPUTE_HOLD', 'PARTIALLY_RELEASED', 'RELEASED', 'PARTIALLY_REFUNDED', 'REFUNDED', 'RECONCILIATION_REQUIRED')",
            name='check_fund_disposition_status',
        ),
    )
    op.create_index('ix_fund_dispositions_status', 'fund_dispositions', ['status'])

    # 4. release_operations
    op.create_table(
        'release_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_operation_reference', sa.String(), nullable=True, unique=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.CheckConstraint('amount_kobo > 0', name='check_release_operation_amount_positive'),
        sa.CheckConstraint(
            "status IN ('DECISION_RECORDED', 'PROVIDER_INITIATED', 'PROVIDER_PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILIATION_REQUIRED')",
            name='check_release_operation_status',
        ),
    )
    op.create_index('ix_release_operations_status', 'release_operations', ['status'])

    # 5. refund_operations
    op.create_table(
        'refund_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_operation_reference', sa.String(), nullable=True, unique=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.CheckConstraint('amount_kobo > 0', name='check_refund_operation_amount_positive'),
        sa.CheckConstraint(
            "status IN ('DECISION_RECORDED', 'PROVIDER_INITIATED', 'PROVIDER_PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILIATION_REQUIRED')",
            name='check_refund_operation_status',
        ),
    )
    op.create_index('ix_refund_operations_status', 'refund_operations', ['status'])

    # 6. disputes
    op.create_table(
        'disputes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False),
        sa.Column('raised_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('raised_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('OPEN', 'RESOLVED_RELEASE', 'RESOLVED_REFUND', 'RESOLVED_PARTIAL')",
            name='check_dispute_status',
        ),
    )
    op.create_index('ix_disputes_fund_disposition_id', 'disputes', ['fund_disposition_id'])
    op.create_index('ix_disputes_status', 'disputes', ['status'])
    op.create_index(
        'ix_disputes_open_unique',
        'disputes',
        ['fund_disposition_id'],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )


def downgrade() -> None:
    op.drop_table('disputes')
    op.drop_table('refund_operations')
    op.drop_table('release_operations')
    op.drop_table('fund_dispositions')
    op.drop_table('payments')
    op.drop_table('payment_attempts')
