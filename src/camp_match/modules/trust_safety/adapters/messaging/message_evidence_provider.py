"""In-process message evidence provider adapter for Trust & Safety."""
from __future__ import annotations

from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard
from camp_match.modules.trust_safety.application.ports.outbound import MessageSnapshotSource
from camp_match.shared_kernel.domain.identifiers import EntityId


class InProcessMessageEvidenceProvider:
    def __init__(self, participant_guard: ParticipantGuard) -> None:
        self._participant_guard = participant_guard

    async def get_message(
        self, viewer_id: EntityId, conversation_id: EntityId, message_id: EntityId
    ) -> MessageSnapshotSource | None:
        try:
            msg = await self._participant_guard.get_message_for_participant(viewer_id, conversation_id, message_id)
            return MessageSnapshotSource(
                message_id=msg.id,
                conversation_id=msg.conversation_id,
                sender_id=msg.sender_id,
                content=msg.content.value,
                sequence=msg.sequence,
                created_at=msg.created_at,
            )
        except Exception:
            return None
