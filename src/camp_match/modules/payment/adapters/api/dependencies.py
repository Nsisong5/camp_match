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
    SqlAlchemyLedgerRepository,
    SqlAlchemyPaymentAttemptRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyRefundOperationRepository,
    SqlAlchemyReleaseDecisionRepository,
    SqlAlchemyReleaseOperationRepository,
    SqlAlchemyReleaseScheduleRepository,
    SqlAlchemyTransactionReviewRepository,
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
from camp_match.config.settings import get_settings
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


def get_release_schedule_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyReleaseScheduleRepository:
    return SqlAlchemyReleaseScheduleRepository(session)


def get_transaction_review_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyTransactionReviewRepository:
    return SqlAlchemyTransactionReviewRepository(session)


def get_dispute_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyDisputeRepository:
    return SqlAlchemyDisputeRepository(session)


def get_webhook_event_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyWebhookEventRepository:
    return SqlAlchemyWebhookEventRepository(session)


def get_release_decision_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyReleaseDecisionRepository:
    return SqlAlchemyReleaseDecisionRepository(session)


def get_ledger_repo(session: Annotated[AsyncSession, Depends(get_db_session)]) -> SqlAlchemyLedgerRepository:
    return SqlAlchemyLedgerRepository(session)


from camp_match.modules.payment.adapters.provider.mock.mock_provider_adapter import (
    MockPaymentProviderAdapter,
)
from camp_match.modules.payment.adapters.provider.paystack.adapter import (
    PaystackPaymentProviderAdapter,
)
from camp_match.modules.payment.adapters.provider.paystack.client import PaystackClient
from camp_match.modules.payment.adapters.provider.paystack.webhook import PaystackWebhookHandler

# ...

_mock_provider = MockPaymentProviderAdapter()

def get_payment_provider(settings: Annotated[Settings, Depends(get_settings)]) -> Any:
    if settings.payment_provider == "paystack":
        client = PaystackClient(settings)
        webhook_handler = PaystackWebhookHandler(settings)
        return PaystackPaymentProviderAdapter(client, webhook_handler)
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


from camp_match.modules.payment.adapters.context.transaction_context_provider import (
    TransactionContextProvider,
)
from camp_match.modules.payment.application.use_cases.evaluate_release_eligibility import (
    EvaluateReleaseEligibilityUseCase,
)
from camp_match.modules.payment.application.use_cases.get_transaction_review import (
    GetTransactionReviewUseCase,
)
from camp_match.modules.payment.application.use_cases.get_transaction_review_summary import (
    GetTransactionReviewSummaryUseCase,
)
from camp_match.modules.payment.application.use_cases.list_payment_tasks import (
    ListPaymentTasksUseCase,
)
from camp_match.modules.payment.application.use_cases.list_transaction_reviews import (
    ListTransactionReviewsUseCase,
)
from camp_match.modules.payment.adapters.security.release_approver_provider import (
    SecurityReleaseApproverProvider,
)
from camp_match.modules.identity.application.use_cases.get_identity import GetIdentityByIdUseCase
from camp_match.modules.security.application.use_cases.list_identities_holding_permission import (
    ListIdentitiesHoldingPermissionUseCase,
)


def get_transaction_context_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionContextProvider:
    return TransactionContextProvider(session)


def get_release_approver_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SecurityReleaseApproverProvider:
    role_repo = SqlAlchemyRoleRepository(session)
    # ...
    return None # Placeholder


def get_evaluate_release_eligibility_use_case(
    fund_disposition_repo: Annotated[
        SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)
    ],
    booking_provider: Annotated[InProcessBookingProvider, Depends(get_booking_provider)],
    dispute_repo: Annotated[SqlAlchemyDisputeRepository, Depends(get_dispute_repo)],
    schedule_repo: Annotated[SqlAlchemyReleaseScheduleRepository, Depends(get_release_schedule_repo)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> EvaluateReleaseEligibilityUseCase:
    # Need approver_provider
    from camp_match.modules.payment.adapters.security.release_approver_provider import SecurityReleaseApproverProvider
    from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
    from camp_match.modules.security.application.use_cases.list_identities_holding_permission import ListIdentitiesHoldingPermissionUseCase
    from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
    from camp_match.modules.identity.application.use_cases.get_identity import GetIdentityByIdUseCase
    
    role_repo = SqlAlchemyRoleRepository(session)
    identity_repo = SqlAlchemyIdentityRepository(session)
    list_identities_uc = ListIdentitiesHoldingPermissionUseCase(role_repo)
    get_identity_uc = GetIdentityByIdUseCase(identity_repo)
    
    approver_provider = SecurityReleaseApproverProvider(list_identities_uc, get_identity_uc)
    
    return EvaluateReleaseEligibilityUseCase(
        fund_disposition_repo,
        booking_provider,
        dispute_repo,
        schedule_repo,
        approver_provider,
        clock,
        get_settings(),
    )


def get_get_transaction_review_use_case(
    review_repo: Annotated[
        SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)
    ],
    payment_repo: Annotated[SqlAlchemyPaymentRepository, Depends(get_payment_repo)],
    attempt_repo: Annotated[
        SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)
    ],
    fd_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    decision_repo: Annotated[SqlAlchemyReleaseDecisionRepository, Depends(get_release_decision_repo)],
    schedule_repo: Annotated[SqlAlchemyReleaseScheduleRepository, Depends(get_release_schedule_repo)],
    dispute_repo: Annotated[SqlAlchemyDisputeRepository, Depends(get_dispute_repo)],
    ledger_repo: Annotated[SqlAlchemyLedgerRepository, Depends(get_ledger_repo)],
    context_provider: Annotated[
        TransactionContextProvider, Depends(get_transaction_context_provider)
    ],
    evaluate_uc: Annotated[
        EvaluateReleaseEligibilityUseCase, Depends(get_evaluate_release_eligibility_use_case)
    ],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> GetTransactionReviewUseCase:
    return GetTransactionReviewUseCase(
        review_repo,
        payment_repo,
        attempt_repo,
        fd_repo,
        decision_repo,
        schedule_repo,
        dispute_repo,
        ledger_repo,
        context_provider,
        evaluate_uc,
        auth_service.authorizer, # Needs to expose authorizer or use auth_service
        clock,
        get_settings(),
    )


def get_list_transaction_reviews_use_case(
    review_repo: Annotated[
        SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)
    ],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> ListTransactionReviewsUseCase:
    return ListTransactionReviewsUseCase(review_repo, auth_service.authorizer)


def get_get_transaction_review_summary_use_case(
    review_repo: Annotated[
        SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)
    ],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> GetTransactionReviewSummaryUseCase:
    return GetTransactionReviewSummaryUseCase(review_repo, auth_service.authorizer, get_settings())


def get_list_payment_tasks_use_case(
    review_repo: Annotated[
        SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)
    ],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ListPaymentTasksUseCase:
    return ListPaymentTasksUseCase(review_repo, auth_service.authorizer, clock, get_settings())


def get_initiate_payment_use_case(
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    booking_provider: Annotated[InProcessBookingProvider, Depends(get_booking_provider)],
    provider: Annotated[Any, Depends(get_payment_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> InitiatePaymentUseCase:
    return InitiatePaymentUseCase(attempt_repo, booking_provider, provider, uow, clock)


def get_verify_payment_attempt_use_case(
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    payment_repo: Annotated[SqlAlchemyPaymentRepository, Depends(get_payment_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    ledger_repo: Annotated[SqlAlchemyLedgerRepository, Depends(get_ledger_repo)],
    provider: Annotated[Any, Depends(get_payment_provider)],
    booking_confirmation_port: Annotated[Any, Depends(get_booking_confirmation_port)],
    booking_provider: Annotated[InProcessBookingProvider, Depends(get_booking_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    review_repo: Annotated[SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)],
) -> VerifyPaymentAttemptUseCase:
    return VerifyPaymentAttemptUseCase(
        attempt_repo,
        payment_repo,
        fund_disposition_repo,
        ledger_repo,
        provider,
        booking_confirmation_port,
        booking_provider,
        uow,
        clock,
        review_repo=review_repo,
    )


def get_process_webhook_use_case(
    webhook_repo: Annotated[SqlAlchemyWebhookEventRepository, Depends(get_webhook_event_repo)],
    attempt_repo: Annotated[SqlAlchemyPaymentAttemptRepository, Depends(get_payment_attempt_repo)],
    provider: Annotated[Any, Depends(get_payment_provider)],
    verify_uc: Annotated[VerifyPaymentAttemptUseCase, Depends(get_verify_payment_attempt_use_case)],
    booking_provider: Annotated[InProcessBookingProvider, Depends(get_booking_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
) -> ProcessWebhookEventUseCase:
    return ProcessWebhookEventUseCase(
        webhook_repo, attempt_repo, provider, verify_uc, booking_provider, uow, clock
    )


def get_execute_release_use_case(
    release_repo: Annotated[SqlAlchemyReleaseOperationRepository, Depends(get_release_operation_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    ledger_repo: Annotated[SqlAlchemyLedgerRepository, Depends(get_ledger_repo)],
    provider: Annotated[Any, Depends(get_payment_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    release_decision_repo: Annotated[SqlAlchemyReleaseDecisionRepository, Depends(get_release_decision_repo)],
    review_repo: Annotated[SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)],
) -> ExecuteReleaseUseCase:
    return ExecuteReleaseUseCase(
        release_repo,
        fund_disposition_repo,
        ledger_repo,
        provider,
        uow,
        clock,
        release_decision_repo=release_decision_repo,
        review_repo=review_repo,
    )


def get_execute_refund_use_case(
    refund_repo: Annotated[SqlAlchemyRefundOperationRepository, Depends(get_refund_operation_repo)],
    fund_disposition_repo: Annotated[SqlAlchemyFundDispositionRepository, Depends(get_fund_disposition_repo)],
    ledger_repo: Annotated[SqlAlchemyLedgerRepository, Depends(get_ledger_repo)],
    provider: Annotated[Any, Depends(get_payment_provider)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)],
    clock: Annotated[SystemClock, Depends(get_clock)],
    review_repo: Annotated[SqlAlchemyTransactionReviewRepository, Depends(get_transaction_review_repo)],
) -> ExecuteRefundUseCase:
    return ExecuteRefundUseCase(
        refund_repo,
        fund_disposition_repo,
        ledger_repo,
        provider,
        uow,
        clock,
        review_repo=review_repo,
    )
