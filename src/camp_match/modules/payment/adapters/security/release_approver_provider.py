"""Release approver provider adapter."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.identity.application.ports.inbound import (
    GetIdentityById,
    IdentityQueryRequest,
)
from camp_match.modules.payment.application.ports.outbound import ReleaseApproverProvider
from camp_match.modules.security.application.ports.inbound import ListIdentitiesHoldingPermission
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger(__name__)


class SecurityReleaseApproverProvider(ReleaseApproverProvider):
    def __init__(
        self,
        list_identities_uc: ListIdentitiesHoldingPermission,
        get_identity_uc: GetIdentityById,
    ) -> None:
        self._list_identities_uc = list_identities_uc
        self._get_identity_uc = get_identity_uc

    async def list_release_approvers(self) -> list[EntityId]:
        try:
            ids = await self._list_identities_uc.execute(Permission.PAYMENT_AUTHORIZE_RELEASE)
            active_ids = []
            for identity_id in ids:
                try:
                    res = await self._get_identity_uc.execute(IdentityQueryRequest(identity_id=str(identity_id)))
                    if res.status == "ACTIVE":
                        active_ids.append(identity_id)
                except Exception as e:
                    logger.warning("approver_status_lookup_failed", identity_id=identity_id, error=str(e))
            return active_ids
        except Exception as e:
            logger.error("list_release_approvers_failed", error=str(e))
            return []

    async def count_active_approvers(self) -> int:
        approvers = await self.list_release_approvers()
        return len(approvers)
