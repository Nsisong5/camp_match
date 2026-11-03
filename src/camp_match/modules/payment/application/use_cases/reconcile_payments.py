from __future__ import annotations

import structlog

from camp_match.modules.payment.application.ports.outbound import (
    FundDispositionRepository,
    PaymentRepository,
)
from camp_match.modules.payment.application.ports.provider import (
    PaymentVerificationCapability,
)
from camp_match.modules.payment.domain.value_objects import (
    FundDispositionStatus,
    PaymentAttemptStatus,
)
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ReconcilePaymentsUseCase:
    def __init__(
        self,
        fund_disposition_repo: FundDispositionRepository,
        payment_repo: PaymentRepository,
        verification_provider: PaymentVerificationCapability,
        uow: UnitOfWork,
    ) -> None:
        self.fund_disposition_repo = fund_disposition_repo
        self.payment_repo = payment_repo
        self.verification_provider = verification_provider
        self.uow = uow

    async def execute(self, disposition_ids: list[EntityId]) -> list[EntityId]:
        flagged: list[EntityId] = []
        for fd_id in disposition_ids:
            fd = await self.fund_disposition_repo.get_by_id(fd_id)
            if not fd or fd.status in {
                FundDispositionStatus.RELEASED,
                FundDispositionStatus.REFUNDED,
                FundDispositionStatus.RECONCILIATION_REQUIRED,
            }:
                continue

            payment = await self.payment_repo.get_by_id(fd.payment_id)
            if not payment:
                async with self.uow:
                    await self.fund_disposition_repo.update_status(
                        fd_id, FundDispositionStatus.RECONCILIATION_REQUIRED
                    )
                    await self.uow.commit()
                flagged.append(fd_id)
                continue

            try:
                verified_tx = await self.verification_provider.verify_transaction(
                    payment.provider_reference
                )
                if (
                    verified_tx.normalized_status != PaymentAttemptStatus.SUCCEEDED
                    or verified_tx.amount.amount_kobo != payment.amount.amount_kobo
                ):
                    async with self.uow:
                        await self.fund_disposition_repo.update_status(
                            fd_id, FundDispositionStatus.RECONCILIATION_REQUIRED
                        )
                        await self.uow.commit()
                    flagged.append(fd_id)
            except Exception as e:
                logger.warning("reconciliation_verification_failed", fd_id=fd_id, error=str(e))
                async with self.uow:
                    await self.fund_disposition_repo.update_status(
                        fd_id, FundDispositionStatus.RECONCILIATION_REQUIRED
                    )
                    await self.uow.commit()
                flagged.append(fd_id)

        return flagged
