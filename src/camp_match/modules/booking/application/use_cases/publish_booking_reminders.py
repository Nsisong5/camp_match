"""Publish booking reminders use case."""
from __future__ import annotations

import structlog
from datetime import timedelta
from typing import Any

from camp_match.modules.booking.adapters.persistence.repository import (
    SqlAlchemyBookingRepository,
)
from camp_match.modules.booking.domain.events import BookingReminderDue
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class PublishBookingRemindersUseCase:
    def __init__(
        self,
        session_factory: Any,
        clock: Clock,
        settings: Any,
    ) -> None:
        self.session_factory = session_factory
        self.clock = clock
        self.settings = settings

    async def __call__(self, limit: int = 100) -> int:
        now = self.clock.now()
        reminders_published = 0

        handover_after = getattr(
            self.settings, "booking_handover_reminder_after_seconds", 86400
        )
        acceptance_after = getattr(
            self.settings, "booking_acceptance_reminder_after_seconds", 86400
        )

        handover_threshold = now - timedelta(seconds=handover_after)
        acceptance_threshold = now - timedelta(seconds=acceptance_after)

        # 1. Handover reminders
        async with self.session_factory() as session:
            repo = SqlAlchemyBookingRepository(session)
            handover_due = await repo.list_due_for_handover_reminder(
                handover_threshold, limit
            )

        for booking in handover_due:
            try:
                async with self.session_factory() as session:
                    repo = SqlAlchemyBookingRepository(session)
                    uow = SqlAlchemyUnitOfWork(session)

                    claimed = await repo.claim_handover_reminder(booking.id, now)
                    if claimed:
                        uow.add_event(
                            BookingReminderDue(
                                booking_id=booking.id,
                                student_id=booking.student_id,
                                property_id=booking.property_id,
                                listing_id=booking.listing_id,
                                reminder_type="HANDOVER_NOT_OFFERED",
                            )
                        )
                        await uow.commit()
                        reminders_published += 1
            except Exception as e:
                logger.warning(
                    "failed_to_publish_handover_reminder",
                    booking_id=booking.id,
                    error=str(e),
                )

        # 2. Acceptance reminders
        async with self.session_factory() as session:
            repo = SqlAlchemyBookingRepository(session)
            acceptance_due = await repo.list_due_for_acceptance_reminder(
                acceptance_threshold, limit
            )

        for booking in acceptance_due:
            try:
                async with self.session_factory() as session:
                    repo = SqlAlchemyBookingRepository(session)
                    uow = SqlAlchemyUnitOfWork(session)

                    claimed = await repo.claim_acceptance_reminder(booking.id, now)
                    if claimed:
                        uow.add_event(
                            BookingReminderDue(
                                booking_id=booking.id,
                                student_id=booking.student_id,
                                property_id=booking.property_id,
                                listing_id=booking.listing_id,
                                reminder_type="ACCEPTANCE_PENDING",
                            )
                        )
                        await uow.commit()
                        reminders_published += 1
            except Exception as e:
                logger.warning(
                    "failed_to_publish_acceptance_reminder",
                    booking_id=booking.id,
                    error=str(e),
                )

        return reminders_published
