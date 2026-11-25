from __future__ import annotations

import structlog
from camp_match.modules.payment.application.ports.outbound import (
    FundDispositionRepository,
    LedgerEntryRepository,
    PaymentAttemptRepository,
    ReleaseOperationRepository,
    RefundOperationRepository,
)
from camp_match.modules.payment.domain.entities import ReleaseOperation, RefundOperation
from camp_match.modules.payment.domain.value_objects import (
    FundDispositionStatus,
    LedgerEntryType,
    OperationStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)

class ApplyOperationOutcome:
    def __init__(
        self,
        release_repo: ReleaseOperationRepository,
        refund_repo: RefundOperationRepository,
        fund_disposition_repo: FundDispositionRepository,
        ledger_repo: LedgerEntryRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.release_repo = release_repo
        self.refund_repo = refund_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.ledger_repo = ledger_repo
        self.uow = uow
        self.clock = clock

    async def execute(
        self,
        operation: ReleaseOperation | RefundOperation,
        status: OperationStatus,
        provider_reference: str | None = None,
        provider_id: str | None = None,
        failure_reason: str | None = None,
        fee_kobo: int | None = None,
        provider_status_detail: str | None = None,
    ) -> None:
        now = self.clock.now()
        
        async with self.uow:
            if isinstance(operation, ReleaseOperation):
                await self.release_repo.update_status(
                    operation.id,
                    status,
                    provider_operation_reference=provider_reference,
                    provider_operation_id=provider_id,
                    provider_fee_kobo=fee_kobo,
                    confirmed_at=now if status == OperationStatus.SUCCEEDED else None,
                    failure_reason=failure_reason,
                )
            else:
                await self.refund_repo.update_status(
                    operation.id,
                    status,
                    provider_operation_reference=provider_reference,
                    provider_operation_id=provider_id,
                    provider_fee_kobo=fee_kobo,
                    provider_status_detail=provider_status_detail,
                    confirmed_at=now if status == OperationStatus.SUCCEEDED else None,
                    failure_reason=failure_reason,
                )

            if status == OperationStatus.SUCCEEDED:
                fd = await self.fund_disposition_repo.get_by_id(operation.fund_disposition_id)
                if fd:
                    if isinstance(operation, ReleaseOperation):
                        fd.add_release_operation(operation)
                        new_status = (
                            FundDispositionStatus.RELEASED
                            if fd.remaining_releasable_kobo == 0
                            else FundDispositionStatus.PARTIALLY_RELEASED
                        )
                        entry_type = LedgerEntryType.RELEASE
                        desc = "Release payout"
                    else:
                        fd.add_refund_operation(operation)
                        new_status = (
                            FundDispositionStatus.REFUNDED
                            if fd.remaining_releasable_kobo == 0
                            else FundDispositionStatus.PARTIALLY_REFUNDED
                        )
                        entry_type = LedgerEntryType.REFUND
                        desc = "Refund"

                    await self.fund_disposition_repo.update_status(operation.fund_disposition_id, new_status)
                    await self.ledger_repo.add(
                        entry_id=EntityId.new(),
                        payment_id=fd.payment_id,
                        fund_disposition_id=operation.fund_disposition_id,
                        entry_type=entry_type,
                        amount_kobo=-operation.amount.amount_kobo,
                        currency=operation.amount.currency.value,
                        reference_type=f"{type(operation).__name__.upper()}_OPERATION",
                        reference_id=operation.id,
                        description=desc,
                        created_at=now,
                    )
            await self.uow.commit()
