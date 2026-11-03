"""Module Messaging: participant_guard.py"""
from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.errors import (
    CommunicationRestricted,
    ConversationNotFound,
)
from camp_match.modules.messaging.domain.entities import Conversation, Message
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import (
        AuthorizationService,
        CommunicationRestrictionProvider,
        ConversationRepository,
        MessageRepository,
    )


class ParticipantGuard:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        restriction_provider: CommunicationRestrictionProvider,
        authorization_service: AuthorizationService,
        message_repo: MessageRepository | None = None,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._restriction_provider = restriction_provider
        self._authorization_service = authorization_service
        self._message_repo = message_repo

    async def require_participant(self, actor_id: EntityId, conversation_id: EntityId) -> Conversation:
        decision = await self._restriction_provider.check(actor_id, None)
        if not decision.allowed:
            raise CommunicationRestricted("You can't send messages in this conversation right now.")

        await self._authorization_service.authorize(actor_id, Permission.MESSAGING_PARTICIPATE)

        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if not conversation or actor_id not in conversation.participant_ids:
            raise ConversationNotFound("Conversation not found.")

        return conversation

    async def get_message_for_participant(self, actor_id: EntityId, conversation_id: EntityId, message_id: EntityId) -> Message:
        await self.require_participant(actor_id, conversation_id)
        if not self._message_repo:
            raise ConversationNotFound("Message not found.")
        message = await self._message_repo.get_by_id(message_id)
        if not message or message.conversation_id != conversation_id:
            raise ConversationNotFound("Message not found.")
        return message
