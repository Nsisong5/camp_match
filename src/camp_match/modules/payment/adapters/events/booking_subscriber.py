"""Booking subscriber adapter for payment module."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.booking.application.ports.events import (
    BookingCancelled,
    BookingExpired,
    BookingInvalidated,
    HandoverAccepted,
    HandoverOffered,
)
from camp_match.modules.payment.adapters.booking.booking_provider import InProcessBookingProvider
from camp_match.modules.payment.adapters.persistence.repository import (
    SqlAlchemyDisputeRepository,
    SqlAlchemyFundDispositionRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyReleaseScheduleRepository,
    SqlAlchemyTransactionReviewRepository,
)
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.payment.application.use_cases.open_release_schedule import (
    OpenReleaseScheduleUseCase,
)
from camp_match.modules.payment.application.use_cases.sync_booking_facts_for_review import (
    SyncBookingFactsForReviewUseCase,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

logger = structlog.get_logger(__name__)


def register_booking_subscribers(
    bus: Any,
    session_factory: Any,
    clock: Any,
    settings: Any,
) -> None:
    async def handle_booking_event(event: Any) -> None:
        try:
            async with session_factory() as session:
                payment_repo = SqlAlchemyPaymentRepository(session)
                fd_repo = SqlAlchemyFundDispositionRepository(session)
                dispute_repo = SqlAlchemyDisputeRepository(session)
                schedule_repo = SqlAlchemyReleaseScheduleRepository(session)
                review_repo = SqlAlchemyTransactionReviewRepository(session)
                booking_repo = SqlAlchemyBookingRepository(session)
                booking_provider = InProcessBookingProvider(booking_repo)
                uow = SqlAlchemyUnitOfWork(session)

                open_schedule_uc = OpenReleaseScheduleUseCase(
                    payment_repo, fd_repo, schedule_repo, review_repo, booking_provider, uow, clock, settings
                )
                sync_uc = SyncBookingFactsForReviewUseCase(
                    payment_repo, fd_repo, dispute_repo, schedule_repo, review_repo, booking_provider, open_schedule_uc, uow, clock
                )
                await sync_uc.execute(event.booking_id)
        except Exception as e:
            logger.error(
                "payment_booking_subscriber_failed",
                error=str(e),
                event_id=getattr(event, "event_id", None),
            )
            raise

    bus.subscribe(HandoverOffered, handle_booking_event)
    bus.subscribe(HandoverAccepted, handle_booking_event)
    bus.subscribe(BookingCancelled, handle_booking_event)
    bus.subscribe(BookingExpired, handle_booking_event)
    bus.subscribe(BookingInvalidated, handle_booking_event)
