from __future__ import annotations

from typing import TYPE_CHECKING

from camp_match.modules.messaging.application.errors import InvalidHistoryCursor
from camp_match.modules.messaging.application.ports.inbound import (
    GetMessageHistoryRequest,
    HistoryPage,
    MessageView,
)
from camp_match.modules.messaging.domain.entities import Message
from camp_match.modules.messaging.domain.value_objects import SequenceCursor
from camp_match.shared_kernel.application.errors import ValidationError
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from camp_match.config.settings import Settings
    from camp_match.modules.messaging.application.ports.outbound import MessageRepository
    from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard


class GetMessageHistoryUseCase:
    def __init__(
        self,
        participant_guard: ParticipantGuard,
        message_repo: MessageRepository,
        settings: Settings,
    ) -> None:
        self._participant_guard = participant_guard
        self._message_repo = message_repo
        self._settings = settings

    async def execute(self, request: GetMessageHistoryRequest) -> HistoryPage:
        # 1. Guard
        await self._participant_guard.require_participant(request.actor_id, request.conversation_id)

        # 2. Limit validation
        if not (1 <= request.limit <= self._settings.messaging_history_max_limit):
            raise ValidationError(f"Limit must be between 1 and {self._settings.messaging_history_max_limit}.")

        # 3. Cursor mutual exclusivity
        if request.before and request.after:
            raise InvalidHistoryCursor("Cannot specify both 'before' and 'after' cursors.")

        # 4. Decode cursors
        before_seq: int | None = None
        after_seq: int | None = None

        try:
            if request.before:
                before_seq = SequenceCursor.decode(request.before)
            if request.after:
                after_seq = SequenceCursor.decode(request.after)
        except ValueError as e:
            raise InvalidHistoryCursor(f"Invalid history cursor: {e}") from e

        # 5. Fetch messages
        has_older = False
        has_newer = False
        older_cursor: str | None = None
        newer_cursor: str | None = None

        if before_seq is not None:
            raw_msgs = await self._message_repo.list_before(request.conversation_id, before_seq, request.limit)
            has_older = len(raw_msgs) > request.limit
            if has_older:
                raw_msgs = raw_msgs[1:]
            older_cursor = SequenceCursor.encode(raw_msgs[0].sequence) if has_older and raw_msgs else None
            newer_cursor = SequenceCursor.encode(raw_msgs[-1].sequence) if raw_msgs else None
            has_newer = True
        elif after_seq is not None:
            raw_msgs = await self._message_repo.list_after(request.conversation_id, after_seq, request.limit)
            has_newer = len(raw_msgs) > request.limit
            if has_newer:
                raw_msgs = raw_msgs[:-1]
            newer_cursor = SequenceCursor.encode(raw_msgs[-1].sequence) if has_newer and raw_msgs else None
            older_cursor = SequenceCursor.encode(raw_msgs[0].sequence) if raw_msgs else None
            has_older = True
        else:
            raw_msgs = await self._message_repo.list_tail(request.conversation_id, request.limit)
            has_older = len(raw_msgs) > request.limit
            if has_older:
                raw_msgs = raw_msgs[1:]
            older_cursor = SequenceCursor.encode(raw_msgs[0].sequence) if has_older and raw_msgs else None
            newer_cursor = None
            has_newer = False

        # 6. Map to MessageView
        items = [self._to_view(m, request.actor_id) for m in raw_msgs]

        return HistoryPage(
            items=items,
            has_older=has_older,
            has_newer=has_newer,
            older_cursor=older_cursor,
            newer_cursor=newer_cursor,
        )

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
