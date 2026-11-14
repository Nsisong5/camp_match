"""add suspension_reason to listings

Revision ID: b1b2c3d4e5f9
Revises: a1b2c3d4e5f8
Create Date: 2026-11-07 14:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'b1b2c3d4e5f9'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('suspension_reason', sa.String(), nullable=True))
    op.create_check_constraint(
        'check_listing_suspension_reason',
        'listings',
        "suspension_reason IS NULL OR suspension_reason IN ('SAFETY_ENFORCEMENT', 'OWNER_ACCOUNT_DISABLED')",
    )
    # Safety backfill for existing SUSPENDED listings
    op.execute(
        "UPDATE listings SET suspension_reason = 'SAFETY_ENFORCEMENT' WHERE status = 'SUSPENDED' AND suspension_reason IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint('check_listing_suspension_reason', 'listings', type_='check')
    op.drop_column('listings', 'suspension_reason')
