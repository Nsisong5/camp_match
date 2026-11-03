from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.errors import CommunicationRestricted
from camp_match.modules.messaging.application.ports.inbound import (
    ConversationView,
    LastMessageView,
    ListConversationsRequest,
    ParticipantView,
)
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.application.pagination import Page

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import (
        AuthorizationService,
        CommunicationRestrictionProvider,
        ConversationRepository,
        MessageRepository,
        ProfileProvider,
    )


class ListConversationsUseCase:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        profile_provider: ProfileProvider,
        restriction_provider: CommunicationRestrictionProvider,
        authorization_service: AuthorizationService,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._profile_provider = profile_provider
        self._restriction_provider = restriction_provider
        self._authorization_service = authorization_service

    async def execute(self, request: ListConversationsRequest) -> Page[ConversationView]:
        decision = await self._restriction_provider.check(request.actor_id, None)
        if not decision.allowed:
            raise CommunicationRestricted("Communication restricted for actor.")

        await self._authorization_service.authorize(request.actor_id, Permission.MESSAGING_PARTICIPATE)

        page = await self._conversation_repo.list_for_participant(request.actor_id, request.page)
        convs = page.items

        if not convs:
            return Page(items=[], total=page.total, page=page.page, page_size=page.page_size)

        conv_ids = [c.id for c in convs]
        last_msgs = await self._message_repo.last_messages(conv_ids)
        unread_map = await self._message_repo.unread_counts(request.actor_id, conv_ids)

        # Batch lookup distinct counterparts
        counterparts = {c.counterpart_of(request.actor_id) for c in convs}
        display_info_map = {}
        for cp_id in counterparts:
            display_info_map[cp_id] = await self._profile_provider.get_display_info(cp_id)

        views = []
        for c in convs:
            cp_id = c.counterpart_of(request.actor_id)
            disp = display_info_map.get(cp_id)
            participant_view = ParticipantView(
                user_id=cp_id,
                profile_id=disp.profile_id if disp else None,
                display_name=disp.display_name if disp else None,
                profile_type=disp.profile_type if disp else None,
            )

            last_msg = last_msgs.get(c.id)
            last_message_view = None
            if last_msg:
                last_message_view = LastMessageView(
                    id=last_msg.id,
                    sender_id=last_msg.sender_id,
                    preview=last_msg.content.value[:100],
                    sequence=last_msg.sequence,
                    created_at=last_msg.created_at,
                )

            unread = unread_map.get(c.id, 0)
            part = await self._conversation_repo.get_participant(c.id, request.actor_id)
            last_read_msg_id = part.last_read_message_id if part else None

            listing_id = c.context.listing_id if c.context.type == "LISTING" else None
            booking_id = c.context.booking_id if c.context.type == "BOOKING" else None

            views.append(
                ConversationView(
                    id=c.id,
                    context_type=c.context.type,
                    listing_id=listing_id,
                    booking_id=booking_id,
                    counterpart=participant_view,
                    last_message=last_message_view,
                    last_activity_at=c.last_activity_at,
                    unread_count=unread,
                    last_read_message_id=last_read_msg_id,
                    created_at=c.created_at,
                )
            )

        return Page(items=views, total=page.total, page=page.page, page_size=page.page_size)
