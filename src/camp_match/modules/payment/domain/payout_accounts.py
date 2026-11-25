from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from camp_match.shared_kernel.domain.identifiers import EntityId

class PayoutAccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REPLACED = "REPLACED"

@dataclass(slots=True)
class PayoutAccount:
    id: EntityId
    scout_id: EntityId
    bank_code: str
    last_four: str
    status: PayoutAccountStatus = PayoutAccountStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    replaced_at: datetime | None = None
    release_hold_until: datetime | None = None
    
    def replace(self, new_account: PayoutAccount, cooloff_hours: int) -> None:
        self.status = PayoutAccountStatus.REPLACED
        self.replaced_at = datetime.now()
        # Logic for release_hold_until will be handled in use case
