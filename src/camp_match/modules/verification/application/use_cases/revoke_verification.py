from __future__ import annotations

import logging
from datetime import datetime, timezone

from camp_match.modules.verification.application.errors import (
    VerificationCaseNotFound,
    InvalidVerificationTransition,
)
from camp_match.modules.verification.application.ports.inbound import (
    RevokeVerificationRequest,
)
from camp_match.modules.verification.application.ports.outbound import (
    HistoryRepository,
    VerificationCaseRepository,
)
from camp_match.modules.verification.domain.value_objects import VerificationStatus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class RevokeVerificationUseCase:
    def __init__(
        self,
        case_repo: VerificationCaseRepository,
        history_repo: HistoryRepository,
        uow: UnitOfWork,
    ):
        self.case_repo = case_repo
        self.history_repo = history_repo
        self.uow = uow

    async def execute(self, request: RevokeVerificationRequest) -> None:
        if not request.revocation_reason or not request.revocation_reason.strip():
            raise InvalidVerificationTransition("Revocation reason is required.")

        case = await self.case_repo.get_by_id(request.case_id)
        if not case:
            raise VerificationCaseNotFound()

        if case.status != VerificationStatus.VERIFIED:
            raise InvalidVerificationTransition("Only VERIFIED cases can be revoked.")

        revoked_at = datetime.now(timezone.utc)

        async with self.uow:
            updated = await self.case_repo.update_status_conditionally(
                case_id=case.id,
                expected_status=VerificationStatus.VERIFIED,
                new_status=VerificationStatus.REVOKED,
                revoked_at=revoked_at,
                revoked_by=request.caller_id,
                revocation_reason=request.revocation_reason,
            )
            if not updated:
                raise InvalidVerificationTransition("Failed to revoke verification case due to state conflict.")

            await self.history_repo.add(
                case_id=case.id,
                event_type="verification_revoked",
                actor_id=request.caller_id,
                details=f"Verification revoked: {request.revocation_reason}",
            )

        logger.warning(
            "verification_revoked_warning: case_id=%s revoked_by=%s reason=%s",
            case.id,
            request.caller_id,
            request.revocation_reason,
        )
