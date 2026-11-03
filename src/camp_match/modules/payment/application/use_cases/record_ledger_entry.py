from __future__ import annotations

import structlog

from camp_match.modules.payment.application.ports.outbound import LedgerEntryRepository
from camp_match.modules.payment.domain.value_objects import LedgerEntryType
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class RecordLedgerEntryUseCase:
    def __init__(
        self,
        ledger_repo: LedgerEntryRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self.ledger_repo = ledger_repo
        self.uow = uow
        self.clock = clock

    async def execute(
        self,
        payment_id: EntityId | None,
        fund_disposition_id: EntityId | None,
        entry_type: LedgerEntryType,
        amount_kobo: int,
        currency: str,
        reference_type: str,
        reference_id: EntityId,
        description: str,
    ) -> None:
        now = self.clock.now()
        entry_id = EntityId.new()

        async with self.uow:
            await self.ledger_repo.add(
                entry_id=entry_id,
                payment_id=payment_id,
                fund_disposition_id=fund_disposition_id,
                entry_type=entry_type,
                amount_kobo=amount_kobo,
                currency=currency,
                reference_type=reference_type,
                reference_id=reference_id,
                description=description,
                created_at=now,
            )
            await self.uow.commit()

        logger.info(
            "ledger_entry_recorded",
            entry_id=entry_id,
            entry_type=entry_type.value,
            amount_kobo=amount_kobo,
        )
