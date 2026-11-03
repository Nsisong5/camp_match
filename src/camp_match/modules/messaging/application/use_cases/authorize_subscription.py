from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.ports.inbound import AuthorizeSubscriptionRequest
from camp_match.modules.messaging.domain.entities import Conversation

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard


class AuthorizeSubscriptionUseCase:
    def __init__(self, participant_guard: ParticipantGuard) -> None:
        self._participant_guard = participant_guard

    async def execute(self, request: AuthorizeSubscriptionRequest) -> Conversation:
        return await self._participant_guard.require_participant(request.actor_id, request.conversation_id)
