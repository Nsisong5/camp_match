"""add release governance persistence tables and constraints

Revision ID: c1b2c3d4e5f1
Revises: b1b2c3d4e5fa
Create Date: 2026-11-15 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1b2c3d4e5f1'
down_revision: str | Sequence[str] | None = 'b1b2c3d4e5fa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add columns and NOT VALID constraints to release_decisions
    op.add_column('release_decisions', sa.Column('student_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('release_decisions', sa.Column('warnings_sent_count', sa.SmallInteger(), nullable=True))
    op.execute(
        "ALTER TABLE release_decisions ADD CONSTRAINT ck_release_requires_student_confirmation "
        "CHECK (decision <> 'RELEASE' OR student_confirmed_at IS NOT NULL) NOT VALID;"
    )
    op.execute(
        "ALTER TABLE release_decisions ADD CONSTRAINT ck_auto_release_requires_three_warnings "
        "CHECK (NOT (decision = 'RELEASE' AND origin = 'AUTOMATIC') OR warnings_sent_count >= 3) NOT VALID;"
    )

    # 2. Create release_schedules table
    op.create_table(
        'release_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False, unique=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_confirmed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cycle', sa.SmallInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('window_starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('cycle >= 1', name='check_release_schedule_cycle_positive'),
    )
    op.create_index('ix_release_schedules_fund_disposition_id', 'release_schedules', ['fund_disposition_id'], unique=True)
    op.create_index('ix_release_schedules_payment_id', 'release_schedules', ['payment_id'])
    op.create_index('ix_release_schedules_booking_id', 'release_schedules', ['booking_id'])

    # 3. Create release_warnings table
    op.create_table(
        'release_warnings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('release_schedule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('release_schedules.id'), nullable=False),
        sa.Column('cycle', sa.SmallInteger(), nullable=False),
        sa.Column('warning_number', sa.SmallInteger(), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('release_schedule_id', 'cycle', 'warning_number', name='uq_release_warning_schedule_cycle_number'),
        sa.CheckConstraint('cycle >= 1', name='check_release_warning_cycle_positive'),
        sa.CheckConstraint('warning_number >= 1', name='check_release_warning_number_positive'),
    )
    op.create_index('ix_release_warnings_release_schedule_id', 'release_warnings', ['release_schedule_id'])
    op.execute(
        "CREATE INDEX ix_release_warnings_due_unsent ON release_warnings (due_at) "
        "WHERE sent_at IS NULL AND superseded_at IS NULL;"
    )

    # 4. Create transaction_reviews table
    op.create_table(
        'transaction_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payments.id'), nullable=False, unique=True),
        sa.Column('fund_disposition_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('fund_dispositions.id'), nullable=False, unique=True),
        sa.Column('payment_attempt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payment_attempts.id'), nullable=False),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('property_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('amount_kobo', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('provider_reference', sa.String(), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('booking_status', sa.String(), nullable=False),
        sa.Column('handover_offered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('handover_accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('student_confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('release_cycle', sa.SmallInteger(), nullable=True),
        sa.Column('release_window_starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warnings_required', sa.SmallInteger(), nullable=True),
        sa.Column('warnings_sent', sa.SmallInteger(), nullable=True),
        sa.Column('last_warning_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('open_dispute_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('dispute_count', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('released_kobo', sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('refunded_kobo', sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('stage', sa.String(), nullable=False),
        sa.Column('next_action', sa.String(), nullable=False),
        sa.Column('next_action_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('version', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
        sa.CheckConstraint('amount_kobo > 0', name='check_transaction_review_amount_positive'),
        sa.CheckConstraint('released_kobo >= 0 AND refunded_kobo >= 0', name='check_transaction_review_ops_positive'),
        sa.CheckConstraint('released_kobo + refunded_kobo <= amount_kobo', name='check_transaction_review_sum_lte_amount'),
    )
    op.create_index('ix_transaction_reviews_payment_id', 'transaction_reviews', ['payment_id'], unique=True)
    op.create_index('ix_transaction_reviews_fund_disposition_id', 'transaction_reviews', ['fund_disposition_id'], unique=True)
    op.create_index('ix_transaction_reviews_payment_attempt_id', 'transaction_reviews', ['payment_attempt_id'])
    op.create_index('ix_transaction_reviews_booking_id', 'transaction_reviews', ['booking_id'])
    op.create_index('ix_transaction_reviews_student_id', 'transaction_reviews', ['student_id'])
    op.create_index('ix_transaction_reviews_stage', 'transaction_reviews', ['stage'])
    op.execute(
        "CREATE INDEX ix_transaction_reviews_next_action ON transaction_reviews (next_action) "
        "WHERE next_action <> 'NONE';"
    )


def downgrade() -> None:
    op.drop_table('transaction_reviews')
    op.drop_table('release_warnings')
    op.drop_table('release_schedules')
    op.execute("ALTER TABLE release_decisions DROP CONSTRAINT IF EXISTS ck_auto_release_requires_three_warnings;")
    op.execute("ALTER TABLE release_decisions DROP CONSTRAINT IF EXISTS ck_release_requires_student_confirmation;")
    op.drop_column('release_decisions', 'warnings_sent_count')
    op.drop_column('release_decisions', 'student_confirmed_at')
