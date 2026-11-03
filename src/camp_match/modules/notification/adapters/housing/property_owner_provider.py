"""Property owner provider adapter for Notification module."""
from __future__ import annotations

from camp_match.modules.housing.application.ports.outbound import PropertyRepository
from camp_match.modules.notification.application.ports.outbound import (
    PropertyOwnerProvider,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class SqlAlchemyPropertyOwnerProvider(PropertyOwnerProvider):
    def __init__(self, property_repo: PropertyRepository) -> None:
        self._property_repo = property_repo

    async def get_owner(self, property_id: EntityId) -> EntityId | None:
        prop = await self._property_repo.get_by_id(property_id)
        if not prop:
            return None
        return prop.provider_id
