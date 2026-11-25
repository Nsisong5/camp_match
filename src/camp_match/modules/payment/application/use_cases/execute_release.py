from __future__ import annotations

import structlog

from camp_match.modules.payment.application.errors import (
    ReleaseNotEligible,
    UnsupportedProviderCapability,
)
from camp_match.modules.payment.application.ports.outbound import (
    FundDispositionRepository,
    LedgerEntryRepository,
    ReleaseDecisionRepository,
    ReleaseOperationRepository,
    TransactionReviewRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    PayoutCapability,
)
from camp_match.modules.payment.application.use_cases.apply_operation_outcome import (
    ApplyOperationOutcome,
)
from camp_match.modules.payment.domain.entities import ReleaseOperation
from camp_match.modules.payment.domain.events import PaymentFundsReleased
from camp_match.modules.payment.domain.value_objects import (
    OperationStatus,
    Money,
    ReviewStage,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class ExecuteReleaseUseCase:
    def __init__(
        self,
        release_repo: ReleaseOperationRepository,
        fund_disposition_repo: FundDispositionRepository,
        ledger_repo: LedgerEntryRepository,
        payout_provider: PayoutCapability,
        uow: UnitOfWork,
        clock: Clock,
        apply_outcome: ApplyOperationOutcome,
        release_decision_repo: ReleaseDecisionRepository | None = None,
        review_repo: TransactionReviewRepository | None = None,
    ) -> None:
        self.release_repo = release_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.ledger_repo = ledger_repo
        self.payout_provider = payout_provider
        self.uow = uow
        self.clock = clock
        self.apply_outcome = apply_outcome
        self.release_decision_repo = release_decision_repo
        self.review_repo = review_repo

    async def execute(
        self,
        decision_id: EntityId,
        fund_disposition_id: EntityId,
        amount: Money,
        recipient_reference: str,
        payout_account_id: EntityId, # Added
    ) -> ReleaseOperation:
        decision = None
        if self.release_decision_repo:
            decision = await self.release_decision_repo.get_by_decision_id(decision_id)
            if decision:
                if decision.decision == "RELEASE":
                    if not decision.student_confirmed_at:
                        logger.error("release_not_eligible_missing_confirmation", decision_id=decision_id)
                        raise ReleaseNotEligible("Student confirmation required for fund release.")
                    if decision.origin == "AUTOMATIC" and (decision.warnings_sent_count or 0) < 3:
                        logger.error("release_not_eligible_insufficient_warnings", decision_id=decision_id)
                        raise ReleaseNotEligible("Three warnings required for automatic release.")

        existing = await self.release_repo.get_by_decision_id(decision_id)
        if existing:
            logger.info("release_operation_idempotent_replay", decision_id=decision_id)
            return existing

        op_id = EntityId.new()
        op = ReleaseOperation(
            id=op_id,
            fund_disposition_id=fund_disposition_id,
            amount=amount,
            status=OperationStatus.DECISION_RECORDED,
            decision_id=decision_id,
            payout_account_id=payout_account_id, # C10
        )

        async with self.uow:
            await self.release_repo.add(op)
            await self.uow.commit()

        if hasattr(self.payout_provider, "capabilities"):
            caps = self.payout_provider.capabilities
            if not caps.supports_payouts:
                await self.apply_outcome.execute(op, OperationStatus.RECONCILIATION_REQUIRED, failure_reason="Unsupported payouts capability")
                logger.error("release_payouts_unsupported", decision_id=decision_id)
                raise UnsupportedProviderCapability("Payout capability not supported by provider.")

        try:
            payout_result = await self.payout_provider.initiate_payout(
                recipient_reference=recipient_reference,
                amount=amount,
                idempotency_key=str(op_id),
            )
        except Exception as e:
            await self.apply_outcome.execute(op, OperationStatus.FAILED, failure_reason=str(e))
            logger.warning("release_payout_failed", decision_id=decision_id, error=str(e))
            raise

        await self.apply_outcome.execute(
            op,
            payout_result.normalized_status,
            provider_reference=payout_result.provider_operation_reference,
            provider_id=payout_result.provider_operation_id,
            failure_reason=payout_result.failure_reason,
            fee_kobo=payout_result.fee_kobo,
        )

        if payout_result.normalized_status == OperationStatus.SUCCEEDED:
            async with self.uow:
                fd = await self.fund_disposition_repo.get_by_id(fund_disposition_id)
                if fd:
                    review = await self.review_repo.get_by_payment_id(fd.payment_id) if self.review_repo else None
                    if review:
                        released_kobo = (review.released_kobo or 0) + amount.amount_kobo
                        new_stage = ReviewStage.RELEASED.value if released_kobo >= review.total_paid_kobo else review.stage
                        await self.review_repo.update_conditional(
                            payment_id=fd.payment_id,
                            expected_version=review.version,
                            values={"released_kobo": released_kobo, "stage": new_stage, "next_action": None},
                        )

                    event = PaymentFundsReleased(
                        payment_id=fd.payment_id,
                        booking_id=fd.booking_id,
                        student_id=review.student_id if review else fd.booking_id,
                        origin=getattr(decision, "origin", "MANUAL"),
                        payout_account_id=payout_account_id, # Added C10
                    )
                    self.uow.add_event(event)
                await self.uow.commit()

        logger.info("execute_release_completed", decision_id=decision_id, status=payout_result.normalized_status.value)
        return op
