from __future__ import annotations

from typing import Protocol

class PayoutRecipientCapability(Protocol):
    async def create_recipient(
        self, account_name: str, bank_code: str, account_number: str
    ) -> str:
        ...
