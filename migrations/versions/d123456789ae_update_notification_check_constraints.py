"""update notification check constraints for category and type

Revision ID: d123456789ae
Revises: d123456789ac
Create Date: 2026-11-08 01:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd123456789ae'
down_revision: str | None = 'd123456789ac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('check_notification_category', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')

    op.create_check_constraint(
        'check_notification_category',
        'notification_notifications',
        "category IN ('MESSAGE', 'BOOKING', 'VERIFICATION', 'SAFETY', 'HOUSING', 'PAYMENT')",
    )
    op.create_check_constraint(
        'check_notification_type',
        'notification_notifications',
        "type IN ("
        "'message.new', 'booking.created.provider', "
        "'booking.confirmed.student', 'booking.confirmed.provider', "
        "'booking.cancelled.student', 'booking.cancelled.provider', "
        "'booking.expired.student', 'verification.verified', "
        "'verification.rejected', 'verification.revoked', "
        "'safety.report_received', 'safety.report_reviewed', "
        "'safety.warning_issued', 'safety.communication_restricted', "
        "'safety.listing_suspended', 'safety.restriction_lifted', "
        "'booking.created.student', 'handover.offered.student', "
        "'handover.accepted.provider', 'booking.handover_reminder.provider', "
        "'booking.acceptance_reminder.student', 'booking.invalidated.student', "
        "'booking.invalidated.provider', 'housing.listing_suspended', "
        "'housing.listing_suspension_lifted', 'payment.failed.student', "
        "'payment.late.student', 'payment.review.student'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint('check_notification_category', 'notification_notifications', type_='check')
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')

    op.create_check_constraint(
        'check_notification_category',
        'notification_notifications',
        "category IN ('MESSAGE', 'BOOKING', 'VERIFICATION', 'SAFETY')",
    )
    op.create_check_constraint(
        'check_notification_type',
        'notification_notifications',
        "type IN ("
        "'message.new', 'booking.created.provider', "
        "'booking.confirmed.student', 'booking.confirmed.provider', "
        "'booking.cancelled.student', 'booking.cancelled.provider', "
        "'booking.expired.student', 'verification.verified', "
        "'verification.rejected', 'verification.revoked', "
        "'safety.report_received', 'safety.report_reviewed', "
        "'safety.warning_issued', 'safety.communication_restricted', "
        "'safety.listing_suspended', 'safety.restriction_lifted'"
        ")",
    )
