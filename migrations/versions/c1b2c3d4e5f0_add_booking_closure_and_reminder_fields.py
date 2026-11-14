"""add booking closure_code and reminder fields

Revision ID: c1b2c3d4e5f0
Revises: b1b2c3d4e5f9
Create Date: 2026-11-07 16:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'c1b2c3d4e5f0'
down_revision: str | Sequence[str] | None = 'b1b2c3d4e5f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('closure_code', sa.String(), nullable=True))
    op.add_column('bookings', sa.Column('handover_reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('acceptance_reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    
    op.create_check_constraint(
        'check_booking_closure_code',
        'bookings',
        "closure_code IS NULL OR closure_code IN ('STUDENT_CANCELLED', 'PROVIDER_CANCELLED', 'STAFF_CANCELLED', 'HOLD_EXPIRED', 'LISTING_SUSPENDED', 'OWNER_ACCOUNT_DISABLED', 'CANCELLED_UNSPECIFIED')",
    )

    # Backfill
    op.execute(
        "UPDATE bookings SET closure_code = 'HOLD_EXPIRED' WHERE status = 'EXPIRED' AND closure_code IS NULL"
    )
    op.execute(
        "UPDATE bookings SET closure_code = 'STUDENT_CANCELLED' WHERE status = 'CANCELLED' AND cancelled_by = student_id AND closure_code IS NULL"
    )
    op.execute(
        "UPDATE bookings SET closure_code = 'CANCELLED_UNSPECIFIED' WHERE status = 'CANCELLED' AND closure_code IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint('check_booking_closure_code', 'bookings', type_='check')
    op.drop_column('bookings', 'acceptance_reminder_sent_at')
    op.drop_column('bookings', 'handover_reminder_sent_at')
    op.drop_column('bookings', 'closure_code')
