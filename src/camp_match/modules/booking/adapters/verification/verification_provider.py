from __future__ import annotations

from camp_match.modules.booking.application.ports.outbound import (
    VerificationProvider,
    VerificationStatusDTO,
)
from camp_match.modules.verification.application.ports.inbound import (
    GetVerificationStatus,
    GetVerificationStatusRequest,
)
from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessVerificationProvider(VerificationProvider):
    def __init__(self, get_verification_status_use_case: GetVerificationStatus) -> None:
        self._get_verification_status_use_case = get_verification_status_use_case

    async def get_verification_status(
        self, target_type: VerificationTargetType, target_id: EntityId
    ) -> VerificationStatusDTO:
        request = GetVerificationStatusRequest(
            target_type=target_type,
            target_id=target_id,
        )
        response = await self._get_verification_status_use_case.execute(request)
        return VerificationStatusDTO(
            is_verified=response.is_verified,
            verified_on=response.verified_on,
        )
