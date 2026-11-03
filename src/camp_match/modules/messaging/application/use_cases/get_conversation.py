from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.ports.inbound import (
    ConversationView,
    GetConversationRequest,
    LastMessageView,
    ParticipantView,
)

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import (
        ConversationRepository,
        MessageRepository,
        ProfileProvider,
    )
    from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard


class GetConversationUseCase:
    def __init__(
        self,
        participant_guard: ParticipantGuard,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        profile_provider: ProfileProvider,
    ) -> None:
        self._participant_guard = participant_guard
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._profile_provider = profile_provider

    async def execute(self, request: GetConversationRequest) -> ConversationView:
        conv = await self._participant_guard.require_participant(request.actor_id, request.conversation_id)

        cp_id = conv.counterpart_of(request.actor_id)
        disp = await self._profile_provider.get_display_info(cp_id)
        participant_view = ParticipantView(
            user_id=cp_id,
            profile_id=disp.profile_id if disp else None,
            display_name=disp.display_name if disp else None,
            profile_type=disp.profile_type if disp else None,
        )

        last_msgs = await self._message_repo.last_messages([conv.id])
        last_msg = last_msgs.get(conv.id)
        last_message_view = None
        if last_msg:
            last_message_view = LastMessageView(
                id=last_msg.id,
                sender_id=last_msg.sender_id,
                preview=last_msg.content.value[:100],
                sequence=last_msg.sequence,
                created_at=last_msg.created_at,
            )

        unread_map = await self._message_repo.unread_counts(request.actor_id, [conv.id])
        unread = unread_map.get(conv.id, 0)

        part = await self._conversation_repo.get_participant(conv.id, request.actor_id)
        last_read_msg_id = part.last_read_message_id if part else None

        listing_id = conv.context.listing_id if conv.context.type == "LISTING" else None
        booking_id = conv.context.booking_id if conv.context.type == "BOOKING" else None

        return ConversationView(
            id=conv.id,
            context_type=conv.context.type,
            listing_id=listing_id,
            booking_id=booking_id,
            counterpart=participant_view,
            last_message=last_message_view,
            last_activity_at=conv.last_activity_at,
            unread_count=unread,
            last_read_message_id=last_read_msg_id,
            created_at=conv.created_at,
        )
