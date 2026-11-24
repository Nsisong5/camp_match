"""add staff payment notification types to check constraint

Revision ID: d123456789ai
Revises: d123456789ah
Create Date: 2026-11-19 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd123456789ai'
down_revision: str | Sequence[str] | None = 'd123456789ah'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')
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
        "'payment.late.student', 'payment.review.student', "
        "'payment.release_due.staff', 'payment.auto_release_warning_first.staff', "
        "'payment.auto_release_warning_reminder.staff', "
        "'payment.auto_release_warning_final.staff', "
        "'payment.dispute_raised.staff', 'payment.funds_auto_released.staff'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint('check_notification_type', 'notification_notifications', type_='check')
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
