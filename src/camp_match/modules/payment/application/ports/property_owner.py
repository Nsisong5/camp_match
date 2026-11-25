from __future__ import annotations

from typing import Protocol

from camp_match.modules.payment.application.ports.provider import PayoutCapability
from camp_match.modules.payment.domain.value_objects import Money

class PropertyOwnerProvider(Protocol):
    async def get_owner_id(self, property_id: str) -> str:
        ...

# Note: PayoutCapability is already defined in src/camp_match/modules/payment/application/ports/provider.py
