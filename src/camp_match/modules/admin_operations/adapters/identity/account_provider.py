from __future__ import annotations

from camp_match.modules.admin_operations.application.ports.outbound import (
    AccountInfo,
    AccountProvider,
)
from camp_match.modules.identity.application.ports.inbound import (
    DisableAccount,
    GetIdentityById,
    IdentityQueryRequest,
    ReactivateAccount,
    UpdateStatusRequest,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessAccountProvider(AccountProvider):
    def __init__(
        self,
        get_identity_uc: GetIdentityById,
        disable_account_uc: DisableAccount,
        reactivate_account_uc: ReactivateAccount,
    ) -> None:
        self._get_identity = get_identity_uc
        self._disable_account = disable_account_uc
        self._reactivate_account = reactivate_account_uc

    async def get(self, identity_id: EntityId) -> AccountInfo | None:
        try:
            resp = await self._get_identity.execute(
                IdentityQueryRequest(identity_id=str(identity_id.value))
            )
            return AccountInfo(
                identity_id=EntityId.from_string(str(resp.id)),
                status=resp.status,
                created_at=resp.created_at,
            )
        except Exception:
            return None

    async def disable(self, identity_id: EntityId, reason: str) -> None:
        await self._disable_account.execute(
            UpdateStatusRequest(identity_id=str(identity_id.value))
        )

    async def reactivate(self, identity_id: EntityId, reason: str) -> None:
        await self._reactivate_account.execute(
            UpdateStatusRequest(identity_id=str(identity_id.value))
        )
