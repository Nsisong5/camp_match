from __future__ import annotations

from typing import TYPE_CHECKING
from camp_match.modules.verification.application.ports.outbound import HousingProvider
from camp_match.modules.housing.adapters.persistence.repository import SqlAlchemyPropertyRepository
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InProcessHousingProvider(HousingProvider):
    def __init__(self, session: AsyncSession) -> None:
        self._property_repo = SqlAlchemyPropertyRepository(session)

    async def get_property_owner(self, property_id: EntityId) -> EntityId | None:
        property_obj = await self._property_repo.get_by_id(property_id)
        if not property_obj:
            return None
        return property_obj.provider_id
