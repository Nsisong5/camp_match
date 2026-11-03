from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.ports.outbound import ParticipantDisplay
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.profile.adapters.persistence.repository import (
        SqlAlchemyProfileRepository,
    )


class InProcessProfileProvider:
    def __init__(self, profile_repo: SqlAlchemyProfileRepository) -> None:
        self._profile_repo = profile_repo

    async def get_display_info(self, identity_id: EntityId) -> ParticipantDisplay | None:
        try:
            profile = await self._profile_repo.get_by_identity_id(identity_id)
            if not profile:
                return None
            ptype = profile.profile_type.value if hasattr(profile.profile_type, "value") else str(profile.profile_type)
            return ParticipantDisplay(
                profile_id=profile.id,
                display_name=profile.display_name,
                profile_type=ptype,
            )
        except Exception:
            return None
