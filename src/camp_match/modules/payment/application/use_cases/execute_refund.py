from __future__ import annotations

import structlog

from camp_match.modules.payment.application.errors import (
    UnsupportedProviderCapability,
)
from camp_match.modules.payment.application.ports.outbound import (
    FundDispositionRepository,
    RefundOperationRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    RefundCapability,
)
from camp_match.modules.payment.domain.entities import RefundOperation
from camp_match.modules.payment.domain.value_objects import (
    FundDispositionStatus,
    Money,
    OperationStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ExecuteRefundUseCase:
    def __init__(
        self,
        refund_repo: RefundOperationRepository,
        fund_disposition_repo: FundDispositionRepository,
        refund_provider: RefundCapability,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.refund_repo = refund_repo
        self.fund_disposition_repo = fund_disposition_repo
        self.refund_provider = refund_provider
        self.uow = uow
        self.clock = clock

    async def execute(
        self,
        decision_id: EntityId,
        fund_disposition_id: EntityId,
        amount: Money,
        provider_reference: str,
    ) -> RefundOperation:
        existing = await self.refund_repo.get_by_decision_id(decision_id)
        if existing:
            logger.info("refund_operation_idempotent_replay", decision_id=decision_id)
            return existing

        now = self.clock.now()
        op_id = EntityId.new()

        op = RefundOperation(
            id=op_id,
            fund_disposition_id=fund_disposition_id,
            amount=amount,
            status=OperationStatus.DECISION_RECORDED,
            decision_id=decision_id,
            requested_at=now,
        )

        async with self.uow:
            await self.refund_repo.add(op)
            await self.uow.commit()

        if hasattr(self.refund_provider, "capabilities"):
            caps = self.refund_provider.capabilities
            if not caps.supports_refunds:
                async with self.uow:
                    await self.refund_repo.update_status(op_id, OperationStatus.RECONCILIATION_REQUIRED, failure_reason="Unsupported refunds capability")
                    await self.uow.commit()
                logger.error("refunds_unsupported", decision_id=decision_id)
                raise UnsupportedProviderCapability("Refund capability not supported by provider.")

        try:
            refund_result = await self.refund_provider.request_refund(
                provider_reference=provider_reference,
                amount=amount,
                idempotency_key=str(op_id),
            )
        except Exception as e:
            async with self.uow:
                await self.refund_repo.update_status(op_id, OperationStatus.FAILED, failure_reason=str(e))
                await self.uow.commit()
            logger.warning("refund_request_failed", decision_id=decision_id, error=str(e))
            raise

        final_op_status = refund_result.normalized_status
        async with self.uow:
            await self.refund_repo.update_status(
                op_id,
                final_op_status,
                provider_operation_reference=refund_result.provider_operation_reference,
                confirmed_at=now if final_op_status == OperationStatus.SUCCEEDED else None,
                failure_reason=refund_result.failure_reason,
            )

            if final_op_status == OperationStatus.SUCCEEDED:
                fd = await self.fund_disposition_repo.get_by_id(fund_disposition_id)
                if fd:
                    fd.add_refund_operation(op)
                    new_status = (
                        FundDispositionStatus.REFUNDED
                        if fd.remaining_releasable_kobo == 0
                        else FundDispositionStatus.PARTIALLY_REFUNDED
                    )
                    await self.fund_disposition_repo.update_status(fund_disposition_id, new_status)

            await self.uow.commit()

        logger.info("execute_refund_completed", decision_id=decision_id, status=final_op_status.value)
        return op
