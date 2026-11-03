from __future__ import annotations

from camp_match.modules.housing.application.ports.outbound import ListingRepository
from camp_match.modules.search.application.ports.outbound import VerificationProvider
from camp_match.modules.search.domain.value_objects import VerificationState
from camp_match.modules.verification.application.ports.inbound import GetVerificationStatusRequest
from camp_match.modules.verification.application.use_cases.get_verification_status import (
    GetVerificationStatusUseCase,
)
from camp_match.modules.verification.domain.value_objects import VerificationTargetType
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessVerificationProvider(VerificationProvider):
    def __init__(self, listing_repository: ListingRepository, get_verification_status_uc: GetVerificationStatusUseCase) -> None:
        self._listing_repository = listing_repository
        self._get_verification_status_uc = get_verification_status_uc

    async def get_verification_states(self, listing_ids: list[EntityId]) -> dict[EntityId, VerificationState]:
        states: dict[EntityId, VerificationState] = {}
        property_cache: dict[EntityId, bool] = {}

        for listing_id in listing_ids:
            listing = await self._listing_repository.get_by_id(listing_id)
            if not listing:
                states[listing_id] = VerificationState.UNVERIFIED
                continue

            property_id = listing.property_id
            if property_id not in property_cache:
                resp = await self._get_verification_status_uc.execute(
                    GetVerificationStatusRequest(
                        target_type=VerificationTargetType.PROPERTY,
                        target_id=property_id,
                    )
                )
                property_cache[property_id] = resp.is_verified

            is_verified = property_cache[property_id]
            states[listing_id] = VerificationState.VERIFIED if is_verified else VerificationState.UNVERIFIED

        return states
