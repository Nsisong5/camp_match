from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.errors import CommunicationRestricted
from camp_match.modules.messaging.application.ports.inbound import AuthorizeConnectionRequest
from camp_match.modules.security.domain.value_objects import Permission

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import (
        AuthorizationService,
        CommunicationRestrictionProvider,
    )


class AuthorizeConnectionUseCase:
    def __init__(
        self,
        restriction_provider: CommunicationRestrictionProvider,
        authorization_service: AuthorizationService,
    ) -> None:
        self._restriction_provider = restriction_provider
        self._authorization_service = authorization_service

    async def execute(self, request: AuthorizeConnectionRequest) -> None:
        decision = await self._restriction_provider.check(request.actor_id, None)
        if not decision.allowed:
            raise CommunicationRestricted("Communication restricted for actor.")

        await self._authorization_service.authorize(request.actor_id, Permission.MESSAGING_PARTICIPATE)
