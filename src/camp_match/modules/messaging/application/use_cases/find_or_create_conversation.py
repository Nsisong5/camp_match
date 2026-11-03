from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from camp_match.modules.messaging.application.errors import (
    CommunicationRestricted,
    ConversationContextNotFound,
    ConversationContextUnavailable,
    RateLimitExceeded,
    SelfConversationNotAllowed,
)
from camp_match.modules.messaging.application.ports.inbound import (
    ConversationView,
    FindOrCreateConversationRequest,
    FindOrCreateResult,
    LastMessageView,
    ParticipantView,
)
from camp_match.modules.messaging.domain.entities import Conversation
from camp_match.modules.messaging.domain.value_objects import ConversationContext
from camp_match.modules.security.domain.value_objects import Permission
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.config.settings import Settings
    from camp_match.modules.messaging.application.ports.outbound import (
        AuthorizationService,
        BookingProvider,
        CommunicationRestrictionProvider,
        ConversationRepository,
        ListingProvider,
        MessageRepository,
        ProfileProvider,
        RateLimiter,
    )


class Clock(Protocol):
    def now(self) -> datetime: ...


class FindOrCreateConversationUseCase:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        listing_provider: ListingProvider,
        booking_provider: BookingProvider,
        profile_provider: ProfileProvider,
        restriction_provider: CommunicationRestrictionProvider,
        rate_limiter: RateLimiter,
        authorization_service: AuthorizationService,
        uow: Any,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._listing_provider = listing_provider
        self._booking_provider = booking_provider
        self._profile_provider = profile_provider
        self._restriction_provider = restriction_provider
        self._rate_limiter = rate_limiter
        self._authorization_service = authorization_service
        self._uow = uow
        self._clock = clock
        self._settings = settings

    async def execute(self, request: FindOrCreateConversationRequest) -> FindOrCreateResult:
        # 1. Rate limit
        rl_res = await self._rate_limiter.check(
            f"conversation_create:{request.actor_id}",
            self._settings.messaging_create_rate_limit,
            self._settings.messaging_create_rate_window_seconds,
        )
        if not rl_res.allowed:
            raise RateLimitExceeded("Too many conversation creation requests.", retry_after_seconds=rl_res.retry_after_seconds)

        # 2. Restriction & participation permission
        decision = await self._restriction_provider.check(request.actor_id, None)
        if not decision.allowed:
            raise CommunicationRestricted("Communication restricted for actor.")

        await self._authorization_service.authorize(request.actor_id, Permission.MESSAGING_PARTICIPATE)

        # 3. Resolve context and counterparts
        counterpart_id: EntityId
        if request.context_type == "LISTING":
            if not request.listing_id or request.booking_id:
                raise ConversationContextNotFound("Invalid listing context parameters.")
            l_ctx = await self._listing_provider.get_listing_context(request.listing_id)
            if not l_ctx:
                raise ConversationContextNotFound("Listing not found.")
            provider_id = l_ctx.provider_id
            if request.actor_id == provider_id:
                raise SelfConversationNotAllowed("Provider cannot start conversation on their own listing.")
            counterpart_id = provider_id
            ctx = ConversationContext(type="LISTING", listing_id=request.listing_id)
            dedupe = ctx.dedupe_key(request.actor_id)
        elif request.context_type == "BOOKING":
            if not request.booking_id or request.listing_id:
                raise ConversationContextNotFound("Invalid booking context parameters.")
            b_ctx = await self._booking_provider.get_booking_context(request.booking_id, request.actor_id)
            if not b_ctx:
                raise ConversationContextNotFound("Booking not found.")
            owner_id = await self._listing_provider.get_property_owner(b_ctx.property_id)
            if not owner_id or (request.actor_id != b_ctx.student_id and request.actor_id != owner_id):
                raise ConversationContextNotFound("Unauthorized booking context access.")
            counterpart_id = owner_id if request.actor_id == b_ctx.student_id else b_ctx.student_id
            ctx = ConversationContext(type="BOOKING", booking_id=request.booking_id)
            dedupe = ctx.dedupe_key(request.actor_id)
        else:
            raise ConversationContextNotFound("Unknown context type.")

        # 4. Check if existing conversation already exists (even if listing/booking status changed later)
        existing = await self._conversation_repo.get_by_dedupe_key(dedupe)
        if existing:
            view = await self._build_view(existing, request.actor_id)
            return FindOrCreateResult(conversation=view, created=False)

        # 5. Validation for new conversation creation
        if request.context_type == "LISTING":
            if l_ctx and l_ctx.status != "PUBLISHED":
                raise ConversationContextUnavailable("Listing is not published.")
        elif request.context_type == "BOOKING":
            if b_ctx and b_ctx.status not in ("AWAITING_PAYMENT", "CONFIRMED"):
                raise ConversationContextUnavailable("Booking is not in active payment/confirmed state.")

        # 6. Restriction check with counterpart
        cp_decision = await self._restriction_provider.check(request.actor_id, counterpart_id)
        if not cp_decision.allowed:
            raise CommunicationRestricted("Communication restricted with counterpart.")

        # 7. Create in UoW
        now = self._clock.now()
        conv = Conversation(
            id=EntityId.new(),
            context=ctx,
            participant_ids=(request.actor_id, counterpart_id),
            dedupe_key=dedupe,
            last_sequence=0,
            last_activity_at=now,
            created_at=now,
        )

        async with self._uow:
            added = await self._conversation_repo.add(conv)
            if not added:
                await self._uow.rollback()
                existing = await self._conversation_repo.get_by_dedupe_key(dedupe)
                if not existing:
                    existing = conv
                view = await self._build_view(existing, request.actor_id)
                return FindOrCreateResult(conversation=view, created=False)
            await self._uow.commit()

        view = await self._build_view(conv, request.actor_id)
        return FindOrCreateResult(conversation=view, created=True)

    async def _build_view(self, conv: Conversation, viewer_id: EntityId) -> ConversationView:
        cp_id = conv.counterpart_of(viewer_id)
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
            content_preview = last_msg.content.value[:100]
            last_message_view = LastMessageView(
                id=last_msg.id,
                sender_id=last_msg.sender_id,
                preview=content_preview,
                sequence=last_msg.sequence,
                created_at=last_msg.created_at,
            )

        unread_dict = await self._message_repo.unread_counts(viewer_id, [conv.id])
        unread = unread_dict.get(conv.id, 0)

        part = await self._conversation_repo.get_participant(conv.id, viewer_id)
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
