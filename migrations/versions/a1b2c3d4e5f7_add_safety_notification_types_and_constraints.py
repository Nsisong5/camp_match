"""add safety notification types and constraints

Revision ID: a1b2c3d4e5f7
Revises: f82b94a10c2f
Create Date: 2026-10-20 12:00:00.000000

"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f7'
down_revision: str | Sequence[str] | None = 'f82b94a10c2f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop existing check constraints on notification_notifications
    op.drop_constraint('check_notification_category', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_target_type', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')

    # Add updated check constraints including SAFETY kinds
    op.create_check_constraint(
        'check_notification_category',
        'notification_notifications',
        "category IN ('MESSAGE', 'BOOKING', 'VERIFICATION', 'SAFETY')"
    )
    op.create_check_constraint(
        'check_notification_target_type',
        'notification_notifications',
        "target_type IS NULL OR target_type IN ('CONVERSATION', 'BOOKING', 'VERIFICATION_CASE', 'SAFETY_REPORT', 'LISTING')"
    )
    op.create_check_constraint(
        'check_notification_type',
        'notification_notifications',
        "type IN ('message.new', 'booking.created.provider', 'booking.confirmed.student', 'booking.confirmed.provider', 'booking.cancelled.student', 'booking.cancelled.provider', 'booking.expired.student', 'verification.verified', 'verification.rejected', 'verification.revoked', 'safety.report_received', 'safety.report_reviewed', 'safety.warning_issued', 'safety.communication_restricted', 'safety.listing_suspended', 'safety.restriction_lifted')"
    )


def downgrade() -> None:
    op.drop_constraint('check_notification_category', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_target_type', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')

    # Restore original check constraints
    op.create_check_constraint(
        'check_notification_category',
        'notification_notifications',
        "category IN ('MESSAGE', 'BOOKING', 'VERIFICATION')"
    )
    op.create_check_constraint(
        'check_notification_target_type',
        'notification_notifications',
        "target_type IS NULL OR target_type IN ('CONVERSATION', 'BOOKING', 'VERIFICATION_CASE')"
    )
    op.create_check_constraint(
        'check_notification_type',
        'notification_notifications',
        "type IN ('message.new', 'booking.created.provider', 'booking.confirmed.student', 'booking.confirmed.provider', 'booking.cancelled.student', 'booking.cancelled.provider', 'booking.expired.student', 'verification.verified', 'verification.rejected', 'verification.revoked')"
    )
