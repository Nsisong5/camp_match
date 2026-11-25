from __future__ import annotations

from typing import Protocol

from camp_match.modules.identity.domain.entities import Account
from camp_match.shared_kernel.domain.identifiers import EntityId


class PayerContactProvider(Protocol):
    async def get_payer_email(self, payer_id: EntityId) -> str:
        ...
