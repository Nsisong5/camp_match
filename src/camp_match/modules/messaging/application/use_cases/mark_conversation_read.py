from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camp_match.modules.messaging.application.errors import InvalidReadPosition
from camp_match.modules.messaging.application.ports.inbound import (
    MarkConversationReadRequest,
    ReadResult,
)

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import (
        ConversationRepository,
        MessageRepository,
    )
    from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard


class MarkConversationReadUseCase:
    def __init__(
        self,
        participant_guard: ParticipantGuard,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        uow: Any,
        clock: Any,
    ) -> None:
        self._participant_guard = participant_guard
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._uow = uow
        self._clock = clock

    async def execute(self, request: MarkConversationReadRequest) -> ReadResult:
        # 1. Guard
        conv = await self._participant_guard.require_participant(request.actor_id, request.conversation_id)

        # 2. Get message in conversation
        msg = await self._message_repo.get_in_conversation(request.conversation_id, request.up_to_message_id)
        if not msg:
            raise InvalidReadPosition("Invalid read position message ID.")

        # 3. Advance read position atomically / conditionally in UoW
        now = self._clock.now()
        async with self._uow:
            await self._message_repo.advance_read_position(
                request.conversation_id,
                request.actor_id,
                msg.sequence,
                msg.id,
                now,
            )
            await self._uow.commit()

        # 4. Fetch updated read message id and unread count
        part = await self._conversation_repo.get_participant(request.conversation_id, request.actor_id)
        last_read_msg_id = part.last_read_message_id if part else None

        unread_dict = await self._message_repo.unread_counts(request.actor_id, [request.conversation_id])
        unread_count = unread_dict.get(request.conversation_id, 0)

        return ReadResult(
            conversation_id=request.conversation_id,
            last_read_message_id=last_read_msg_id,
            unread_count=unread_count,
        )
