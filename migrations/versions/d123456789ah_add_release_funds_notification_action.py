"""add release funds notification action

Revision ID: d123456789ah
Revises: c1b2c3d4e5f1
Create Date: 2026-11-16 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd123456789ah'
down_revision: str | Sequence[str] | None = 'c1b2c3d4e5f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('check_notification_action', 'notification_notifications', type_='check')
    op.create_check_constraint(
        'check_notification_action',
        'notification_notifications',
        "action IS NULL OR action IN ('COMPLETE_PAYMENT', 'OFFER_HANDOVER', 'ACCEPT_HANDOVER', 'RELEASE_FUNDS')",
    )


def downgrade() -> None:
    op.drop_constraint('check_notification_action', 'notification_notifications', type_='check')
    op.create_check_constraint(
        'check_notification_action',
        'notification_notifications',
        "action IS NULL OR action IN ('COMPLETE_PAYMENT', 'OFFER_HANDOVER', 'ACCEPT_HANDOVER')",
    )
