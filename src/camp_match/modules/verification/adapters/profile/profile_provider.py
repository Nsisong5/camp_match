from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.domain.value_objects import ProfileType
from camp_match.modules.verification.application.ports.outbound import ProfileProvider
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InProcessProfileProvider(ProfileProvider):
    def __init__(self, session: AsyncSession) -> None:
        self._profile_repo = SqlAlchemyProfileRepository(session)

    async def is_scout(self, identity_id: EntityId) -> bool:
        profile = await self._profile_repo.get_by_id(identity_id)
        if not profile:
            return False
        return profile.profile_type == ProfileType.SCOUT
