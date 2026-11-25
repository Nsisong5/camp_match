from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta

from camp_match.modules.payment.application.ports.payout_recipient import PayoutRecipientCapability
from camp_match.modules.payment.domain.payout_accounts import PayoutAccount, PayoutAccountStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.identifiers import EntityId
from camp_match.config.settings import Settings

class SetPayoutAccountUseCase:
    def __init__(
        self,
        payout_account_repo: Any, # SqlAlchemyPayoutAccountRepository
        recipient_provider: PayoutRecipientCapability,
        uow: UnitOfWork,
        settings: Settings,
    ) -> None:
        self.payout_account_repo = payout_account_repo
        self.recipient_provider = recipient_provider
        self.uow = uow
        self.settings = settings

    async def execute(
        self, scout_id: EntityId, account_name: str, bank_code: str, account_number: str
    ) -> PayoutAccount:
        async with self.uow:
            existing = await self.payout_account_repo.get_active_by_scout_id(scout_id)
            
            # Idempotency check: same bank and last 4
            if existing and existing.bank_code == bank_code and existing.last_four == account_number[-4:]:
                return existing

            recipient_code = await self.recipient_provider.create_recipient(
                account_name, bank_code, account_number
            )
            
            new_account = PayoutAccount(
                id=EntityId.new(),
                scout_id=scout_id,
                bank_code=bank_code,
                last_four=account_number[-4:],
                status=PayoutAccountStatus.ACTIVE
            )
            
            if existing:
                new_account.release_hold_until = datetime.now() + timedelta(hours=self.settings.payout_account_change_cooloff_hours)
                await self.payout_account_repo.replace_account(existing.id, new_account)
            else:
                await self.payout_account_repo.add(new_account)
            
            await self.uow.commit()
            return new_account
