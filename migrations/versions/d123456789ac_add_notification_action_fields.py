"""add notification action and resolved_at fields

Revision ID: d123456789ac
Revises: c1b2c3d4e5f0
Create Date: 2026-11-07 17:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'd123456789ac'
down_revision: str | Sequence[str] | None = 'c1b2c3d4e5f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('notification_notifications', sa.Column('action', sa.String(), nullable=True))
    op.add_column('notification_notifications', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    
    op.create_check_constraint(
        'check_notification_action',
        'notification_notifications',
        "action IS NULL OR action IN ('COMPLETE_PAYMENT', 'OFFER_HANDOVER', 'ACCEPT_HANDOVER')",
    )

    op.execute(
        "CREATE INDEX ix_notifications_action_required ON notification_notifications (recipient_id) WHERE action IS NOT NULL AND resolved_at IS NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notifications_action_required;")
    op.drop_constraint('check_notification_action', 'notification_notifications', type_='check')
    op.drop_column('notification_notifications', 'resolved_at')
    op.drop_column('notification_notifications', 'action')
