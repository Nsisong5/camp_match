from __future__ import annotations

from typing import Any

from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.payment.adapters.booking.booking_provider import InProcessBookingProvider
from camp_match.modules.payment.adapters.persistence.repository import (
    SqlAlchemyDisputeRepository,
    SqlAlchemyFundDispositionRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyReleaseScheduleRepository,
    SqlAlchemyTransactionReviewRepository,
)
from camp_match.modules.payment.application.use_cases.open_release_schedule import OpenReleaseScheduleUseCase
from camp_match.modules.payment.application.use_cases.reconcile_transaction_reviews import (
    ReconcileTransactionReviewsUseCase,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus


def build_payment_review_reconcile_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    async def run() -> None:
        async with session_factory() as db_session:
            payment_repo = SqlAlchemyPaymentRepository(db_session)
            fd_repo = SqlAlchemyFundDispositionRepository(db_session)
            booking_repo = SqlAlchemyBookingRepository(db_session)
            booking_provider = InProcessBookingProvider(booking_repo)
            dispute_repo = SqlAlchemyDisputeRepository(db_session)
            schedule_repo = SqlAlchemyReleaseScheduleRepository(db_session)
            review_repo = SqlAlchemyTransactionReviewRepository(db_session)
            uow = SqlAlchemyUnitOfWork(db_session)

            open_schedule_uc = OpenReleaseScheduleUseCase(
                fund_disposition_repo=fd_repo,
                booking_provider=booking_provider,
                dispute_repo=dispute_repo,
                schedule_repo=schedule_repo,
                review_repo=review_repo,
                uow=uow,
                clock=clock,
            )
            uc = ReconcileTransactionReviewsUseCase(
                payment_repo=payment_repo,
                fund_disposition_repo=fd_repo,
                booking_provider=booking_provider,
                dispute_repo=dispute_repo,
                schedule_repo=schedule_repo,
                review_repo=review_repo,
                open_schedule_uc=open_schedule_uc,
                uow=uow,
                clock=clock,
            )
            await uc.execute()

    return run
