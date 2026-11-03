"""Payment API dependencies."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.booking.application.use_cases.confirm_booking import ConfirmBookingUseCase
from camp_match.modules.payment.adapters.booking.booking_provider import InProcessBookingProvider
from camp_match.modules.payment.adapters.persistence.repository import (
    SqlAlchemyDisputeRepository,
    SqlAlchemyFundDispositionRepository,
    SqlAlchemyPaymentAttemptRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyRefundOperationRepository,
    SqlAlchemyReleaseDecisionRepository,
    SqlAlchemyReleaseOperationRepository,
    SqlAlchemyWebhookEventRepository,
)
from camp_match.modules.payment.adapters.provider.mock.mock_provider_adapter import (
    MockPaymentProviderAdapter,
)
from camp_match.modules.payment.adapters.security.authorization import InProcessAuthorizationService
from camp_match.modules.payment.application.use_cases.execute_refund import ExecuteRefundUseCase
from camp_match.modules.payment.application.use_cases.execute_release import ExecuteReleaseUseCase
from camp_match.modules.payment.application.use_cases.initiate_payment import InitiatePaymentUseCase
from camp_match.modules.payment.application.use_cases.process_webhook_event import (
    ProcessWebhookEventUseCase,
)
from camp_match.modules.payment.application.use_cases.verify_payment_attempt import (
    VerifyPaymentAttemptUseCase,
)
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.platform.clock import SystemClock, get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus


def get_uow(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_booking_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyBookingRepository:
    return SqlAlchemyBookingRepository(session)


def get_payment_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyPaymentRepository:
    return SqlAlchemyPaymentRepository(session)


def get_payment_attempt_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyPaymentAttemptRepository:
    return SqlAlchemyPaymentAttemptRepository(session)


def get_fund_disposition_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyFundDispositionRepository:
    return SqlAlchemyFundDispositionRepository(session)


def get_release_operation_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyReleaseOperationRepository:
    return SqlAlchemyReleaseOperationRepository(session)


def get_refund_operation_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyRefundOperationRepository:
    return SqlAlchemyRefundOperationRepository(session)


def get_dispute_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyDisputeRepository:
    return SqlAlchemyDisputeRepository(session)


def get_webhook_event_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyWebhookEventRepository:
    return SqlAlchemyWebhookEventRepository(session)


def get_release_decision_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyReleaseDecisionRepository:
    return SqlAlchemyReleaseDecisionRepository(session)


_mock_provider = MockPaymentProviderAdapter()


def get_mock_provider() -> MockPaymentProviderAdapter:
    return _mock_provider


def get_authorization_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessAuthorizationService:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizationService(authorize_uc)


def get_booking_confirmation_port(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> Any:
    class BookingConfirmationAdapter:
        async def confirm_booking(self, booking_id, caller_id) -> bool:
            try:
                uc = ConfirmBookingUseCase(booking_repo, auth_service, uow, clock, get_event_bus())
                await uc.execute(type("Req", (), {"booking_id": booking_id, "caller_id": caller_id})())
                return True
            except Exception:
                return False
    return BookingConfirmationAdapter()


def get_booking_provider(
    booking_repo: Annotated[SqlAlchemyBookingRepository, Depends(get_booking_repo)],
) -> InProcessBookingProvider:
    return InProcessBookingProvider(booking_repo)


def get_initiate_payment_use_case(
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    booking_provider: Annotated[InProcessBookingProvider, Depends(get_booking_provider)],
    provider: Annotated[MockPaymentProviderAdapter, Depends(get_mock_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> InitiatePaymentUseCase:
    return InitiatePaymentUseCase(attempt_repo, booking_provider, provider, uow, clock)


def get_verify_payment_attempt_use_case(
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    payment_repo: Annotated[SqlAlchemyPaymentRepository, Depends(get_payment_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    provider: Annotated[MockPaymentProviderAdapter, Depends(get_mock_provider)],
    booking_confirmation_port: Annotated[Any, Depends(get_booking_confirmation_port)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> VerifyPaymentAttemptUseCase:
    return VerifyPaymentAttemptUseCase(
        attempt_repo,
        payment_repo,
        fund_disposition_repo,
        provider,
        booking_confirmation_port,
        uow,
        clock,
    )


def get_process_webhook_use_case(
    webhook_repo: Annotated[SqlAlchemyWebhookEventRepository, Depends(get_webhook_event_repo)],
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    provider: Annotated[MockPaymentProviderAdapter, Depends(get_mock_provider)],
    verify_uc: Annotated[VerifyPaymentAttemptUseCase, Depends(get_verify_payment_attempt_use_case)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ProcessWebhookEventUseCase:
    return ProcessWebhookEventUseCase(
        webhook_repo, attempt_repo, provider, verify_uc, uow, clock
    )


def get_execute_release_use_case(
    release_repo: Annotated[SqlAlchemyReleaseOperationRepository, Depends(get_release_operation_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    provider: Annotated[MockPaymentProviderAdapter, Depends(get_mock_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ExecuteReleaseUseCase:
    return ExecuteReleaseUseCase(release_repo, fund_disposition_repo, provider, uow, clock)


def get_execute_refund_use_case(
    refund_repo: Annotated[SqlAlchemyRefundOperationRepository, Depends(get_refund_operation_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    provider: Annotated[MockPaymentProviderAdapter, Depends(get_mock_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ExecuteRefundUseCase:
    return ExecuteRefundUseCase(refund_repo, fund_disposition_repo, provider, uow, clock)
