from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from camp_match.modules.messaging.application.errors import (
    ClientMessageIdConflict,
    CommunicationRestricted,
    DuplicateClientMessageId,
    InvalidClientMessageId,
    InvalidMessageContent,
    RateLimitExceeded,
)
from camp_match.modules.messaging.application.ports.inbound import (
    MessageView,
    RealtimeEvent,
    SendMessageRequest,
    SendMessageResult,
)
from camp_match.modules.messaging.domain.entities import Message
from camp_match.modules.messaging.domain.events import MessageCreated
from camp_match.modules.messaging.domain.value_objects import (
    ClientMessageId,
    MessageContent,
    SequenceCursor,
)
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.config.settings import Settings
    from camp_match.modules.messaging.application.ports.outbound import (
        CommunicationRestrictionProvider,
        MessageEventDispatcher,
        MessageRepository,
        OutboxRepository,
        RateLimiter,
        RealtimeGateway,
    )
    from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard

logger = structlog.get_logger()


class SendMessageUseCase:
    def __init__(
        self,
        participant_guard: ParticipantGuard,
        message_repo: MessageRepository,
        outbox_repo: OutboxRepository,
        restriction_provider: CommunicationRestrictionProvider,
        rate_limiter: RateLimiter,
        realtime_gateway: RealtimeGateway,
        message_event_dispatcher: MessageEventDispatcher,
        uow: Any,
        clock: Any,
        settings: Settings,
    ) -> None:
        self._participant_guard = participant_guard
        self._message_repo = message_repo
        self._outbox_repo = outbox_repo
        self._restriction_provider = restriction_provider
        self._rate_limiter = rate_limiter
        self._realtime_gateway = realtime_gateway
        self._message_event_dispatcher = message_event_dispatcher
        self._uow = uow
        self._clock = clock
        self._settings = settings

    async def execute(self, request: SendMessageRequest) -> SendMessageResult:
        # 1. Rate limit
        rl_res = await self._rate_limiter.check(
            f"message_send:{request.actor_id}",
            self._settings.messaging_send_rate_limit,
            self._settings.messaging_send_rate_window_seconds,
        )
        if not rl_res.allowed:
            raise RateLimitExceeded("Too many message send requests.", retry_after_seconds=rl_res.retry_after_seconds)

        # 2. Guard (restriction, participation permission, conversation membership)
        conv = await self._participant_guard.require_participant(request.actor_id, request.conversation_id)
        counterpart_id = conv.counterpart_of(request.actor_id)

        # 3. Counterpart restriction check
        decision = await self._restriction_provider.check(request.actor_id, counterpart_id)
        if not decision.allowed:
            raise CommunicationRestricted("Communication restricted with counterpart.")

        # 4. Content validation (must happen after auth checks)
        try:
            msg_content = MessageContent.create(request.content, self._settings.messaging_max_message_length)
        except ValueError as e:
            raise InvalidMessageContent(str(e)) from e

        # 5. Client message ID validation
        try:
            client_msg_id = ClientMessageId(request.client_message_id)
        except ValueError as e:
            raise InvalidClientMessageId(str(e)) from e

        # 6. Idempotency pre-check
        existing = await self._message_repo.get_by_client_message_id(request.actor_id, request.client_message_id)
        if existing:
            if existing.conversation_id == request.conversation_id and existing.content.value == msg_content.value:
                return SendMessageResult(message=self._to_view(existing, request.actor_id), replayed=True)
            else:
                raise ClientMessageIdConflict("Client message ID conflict.")

        # 7. Atomic transaction: sequence bump + message add + outbox add
        now = self._clock.now()
        async with self._uow:
            try:
                sequence = await self._message_repo.next_sequence(request.conversation_id, now)
                message = Message(
                    id=EntityId.new(),
                    conversation_id=request.conversation_id,
                    sender_id=request.actor_id,
                    sequence=sequence,
                    content=msg_content,
                    client_message_id=client_msg_id,
                    created_at=now,
                )
                await self._message_repo.add(message)

                event = MessageCreated(
                    message_id=message.id,
                    conversation_id=request.conversation_id,
                    sender_id=request.actor_id,
                    recipient_id=counterpart_id,
                    sequence=sequence,
                    context_type=conv.context.type,
                    message_created_at=message.created_at,
                )
                await self._outbox_repo.add(event)
                await self._uow.commit()
            except DuplicateClientMessageId:
                await self._uow.rollback()
                reloaded = await self._message_repo.get_by_client_message_id(request.actor_id, request.client_message_id)
                if reloaded and reloaded.conversation_id == request.conversation_id and reloaded.content.value == msg_content.value:
                    return SendMessageResult(message=self._to_view(reloaded, request.actor_id), replayed=True)
                raise ClientMessageIdConflict("Client message ID conflict.") from None

        # 8. Post-commit best-effort steps (each wrapped independently, never log message content)
        try:
            rt_event = RealtimeEvent(
                type="message.created",
                conversation_id=request.conversation_id,
                event_id=event.event_id,
                payload=event.to_payload(),
            )
            await self._realtime_gateway.push([request.actor_id, counterpart_id], rt_event)
        except Exception as e:
            logger.warning("realtime_push_failed", error=str(e), conversation_id=str(request.conversation_id))

        try:
            await self._message_event_dispatcher.dispatch(event.event_id)
        except Exception as e:
            logger.warning("event_dispatch_failed", error=str(e), event_id=str(event.event_id))

        return SendMessageResult(message=self._to_view(message, request.actor_id), replayed=False)

    def _to_view(self, msg: Message, viewer_id: EntityId) -> MessageView:
        cmid = msg.client_message_id.value if msg.sender_id == viewer_id else None
        return MessageView(
            id=msg.id,
            conversation_id=msg.conversation_id,
            sender_id=msg.sender_id,
            content=msg.content.value,
            sequence=msg.sequence,
            cursor=SequenceCursor.encode(msg.sequence),
            created_at=msg.created_at,
            client_message_id=cmid,
        )
