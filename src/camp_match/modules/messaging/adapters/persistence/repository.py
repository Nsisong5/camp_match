from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from camp_match.modules.messaging.adapters.persistence.models import (
    MessagingConversationModel,
    MessagingMessageModel,
    MessagingParticipantModel,
    MessagingRestrictionModel,
)
from camp_match.modules.messaging.application.errors import DuplicateClientMessageId
from camp_match.modules.messaging.domain.entities import (
    CommunicationRestriction,
    Conversation,
    ConversationParticipant,
    Message,
)
from camp_match.modules.messaging.domain.value_objects import (
    ClientMessageId,
    ConversationContext,
    MessageContent,
)
from camp_match.shared_kernel.application.pagination import Page, PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, conversation: Conversation) -> bool:
        listing_id = conversation.context.listing_id.value if conversation.context.listing_id else None
        booking_id = conversation.context.booking_id.value if conversation.context.booking_id else None

        stmt = insert(MessagingConversationModel).values(
            id=conversation.id.value,
            context_type=conversation.context.type,
            listing_id=listing_id,
            booking_id=booking_id,
            dedupe_key=conversation.dedupe_key,
            last_sequence=conversation.last_sequence,
            last_activity_at=conversation.last_activity_at or conversation.created_at or datetime.now(),
            created_at=conversation.created_at or datetime.now(),
        ).on_conflict_do_nothing(index_elements=["dedupe_key"])

        result = await self._session.execute(stmt)
        if cast(int, getattr(result, "rowcount", 0)) == 0:
            return False

        for pid in conversation.participant_ids:
            part_model = MessagingParticipantModel(
                conversation_id=conversation.id.value,
                user_id=pid.value,
                joined_at=conversation.created_at or datetime.now(),
                last_read_sequence=0,
            )
            self._session.add(part_model)

        await self._session.flush()
        return True

    async def get_by_id(self, conversation_id: EntityId) -> Conversation | None:
        stmt = select(MessagingConversationModel).where(MessagingConversationModel.id == conversation_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return await self._to_domain(model)

    async def get_by_dedupe_key(self, dedupe_key: str) -> Conversation | None:
        stmt = select(MessagingConversationModel).where(MessagingConversationModel.dedupe_key == dedupe_key)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return await self._to_domain(model)

    async def list_for_participant(self, user_id: EntityId, page_request: PageRequest) -> Page[Conversation]:
        conv_ids_stmt = (
            select(MessagingParticipantModel.conversation_id)
            .where(MessagingParticipantModel.user_id == user_id.value)
        )
        
        base_stmt = (
            select(MessagingConversationModel)
            .where(MessagingConversationModel.id.in_(conv_ids_stmt))
            .order_by(MessagingConversationModel.last_activity_at.desc(), MessagingConversationModel.id.desc())
        )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_res = await self._session.execute(count_stmt)
        total = total_res.scalar_one()

        offset = (page_request.page - 1) * page_request.page_size
        stmt = base_stmt.offset(offset).limit(page_request.page_size)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        items = []
        for m in models:
            items.append(await self._to_domain(m))

        return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)

    async def get_participant(self, conversation_id: EntityId, user_id: EntityId) -> ConversationParticipant | None:
        stmt = select(MessagingParticipantModel).where(
            MessagingParticipantModel.conversation_id == conversation_id.value,
            MessagingParticipantModel.user_id == user_id.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return ConversationParticipant(
            conversation_id=EntityId(model.conversation_id),
            user_id=EntityId(model.user_id),
            joined_at=model.joined_at,
            last_read_sequence=model.last_read_sequence,
            last_read_message_id=EntityId(model.last_read_message_id) if model.last_read_message_id else None,
            last_read_at=model.last_read_at,
        )

    async def _to_domain(self, model: MessagingConversationModel) -> Conversation:
        part_stmt = select(MessagingParticipantModel.user_id).where(MessagingParticipantModel.conversation_id == model.id)
        part_res = await self._session.execute(part_stmt)
        user_ids = [EntityId(uid) for uid in part_res.scalars().all()]
        
        ctx = ConversationContext(
            type=model.context_type,
            listing_id=EntityId(model.listing_id) if model.listing_id else None,
            booking_id=EntityId(model.booking_id) if model.booking_id else None,
        )

        return Conversation(
            id=EntityId(model.id),
            context=ctx,
            participant_ids=(user_ids[0], user_ids[1]) if len(user_ids) == 2 else tuple(user_ids), # type: ignore
            dedupe_key=model.dedupe_key,
            last_sequence=model.last_sequence,
            last_activity_at=model.last_activity_at,
            created_at=model.created_at,
        )


class SqlAlchemyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_sequence(self, conversation_id: EntityId, message_created_at: datetime) -> int:
        stmt = (
            update(MessagingConversationModel)
            .where(MessagingConversationModel.id == conversation_id.value)
            .values(
                last_sequence=MessagingConversationModel.last_sequence + 1,
                last_activity_at=func.greatest(MessagingConversationModel.last_activity_at, message_created_at),
                updated_at=func.now(),
            )
            .returning(MessagingConversationModel.last_sequence)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Conversation {conversation_id} not found for sequence bump.")
        return row

    async def add(self, message: Message) -> None:
        model = MessagingMessageModel(
            id=message.id.value,
            conversation_id=message.conversation_id.value,
            sender_id=message.sender_id.value,
            sequence=message.sequence,
            content=message.content.value,
            client_message_id=message.client_message_id.value,
            created_at=message.created_at,
        )
        try:
            self._session.add(model)
            await self._session.flush()
        except IntegrityError as e:
            orig_msg = str(e.orig).lower()
            if "uq_messaging_messages_sender_client_message_id" in orig_msg or "client_message_id" in orig_msg:
                raise DuplicateClientMessageId("Duplicate client message ID.") from e
            raise

    async def get_by_client_message_id(self, sender_id: EntityId, client_message_id: str) -> Message | None:
        stmt = select(MessagingMessageModel).where(
            MessagingMessageModel.sender_id == sender_id.value,
            MessagingMessageModel.client_message_id == client_message_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_in_conversation(self, conversation_id: EntityId, message_id: EntityId) -> Message | None:
        stmt = select(MessagingMessageModel).where(
            MessagingMessageModel.conversation_id == conversation_id.value,
            MessagingMessageModel.id == message_id.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_tail(self, conversation_id: EntityId, limit: int) -> list[Message]:
        stmt = (
            select(MessagingMessageModel)
            .where(MessagingMessageModel.conversation_id == conversation_id.value)
            .order_by(MessagingMessageModel.sequence.desc())
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        models.reverse()
        return [self._to_domain(m) for m in models]

    async def list_before(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        stmt = (
            select(MessagingMessageModel)
            .where(
                MessagingMessageModel.conversation_id == conversation_id.value,
                MessagingMessageModel.sequence < sequence,
            )
            .order_by(MessagingMessageModel.sequence.desc())
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        models.reverse()
        return [self._to_domain(m) for m in models]

    async def list_after(self, conversation_id: EntityId, sequence: int, limit: int) -> list[Message]:
        stmt = (
            select(MessagingMessageModel)
            .where(
                MessagingMessageModel.conversation_id == conversation_id.value,
                MessagingMessageModel.sequence > sequence,
            )
            .order_by(MessagingMessageModel.sequence.asc())
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def last_messages(self, conversation_ids: list[EntityId]) -> dict[EntityId, Message]:
        if not conversation_ids:
            return {}
        conv_uuids = [cid.value for cid in conversation_ids]
        
        subq = (
            select(
                MessagingMessageModel.conversation_id,
                MessagingMessageModel.sequence,
            )
            .join(
                MessagingConversationModel,
                MessagingConversationModel.id == MessagingMessageModel.conversation_id,
            )
            .where(
                MessagingMessageModel.conversation_id.in_(conv_uuids),
                MessagingMessageModel.sequence == MessagingConversationModel.last_sequence,
            )
            .subquery()
        )

        stmt = select(MessagingMessageModel).join(
            subq,
            (MessagingMessageModel.conversation_id == subq.c.conversation_id) &
            (MessagingMessageModel.sequence == subq.c.sequence),
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return {EntityId(m.conversation_id): self._to_domain(m) for m in models}

    async def unread_counts(self, user_id: EntityId, conversation_ids: list[EntityId]) -> dict[EntityId, int]:
        if not conversation_ids:
            return {}
        conv_uuids = [cid.value for cid in conversation_ids]

        stmt = (
            select(
                MessagingMessageModel.conversation_id,
                func.count(),
            )
            .join(
                MessagingParticipantModel,
                (MessagingParticipantModel.conversation_id == MessagingMessageModel.conversation_id) &
                (MessagingParticipantModel.user_id == user_id.value),
            )
            .where(
                MessagingMessageModel.conversation_id.in_(conv_uuids),
                MessagingMessageModel.sender_id != user_id.value,
                MessagingMessageModel.sequence > MessagingParticipantModel.last_read_sequence,
            )
            .group_by(MessagingMessageModel.conversation_id)
        )
        result = await self._session.execute(stmt)
        counts = {EntityId(row[0]): row[1] for row in result.all()}
        return {cid: counts.get(cid, 0) for cid in conversation_ids}

    async def advance_read_position(
        self,
        conversation_id: EntityId,
        user_id: EntityId,
        sequence: int,
        message_id: EntityId,
        at: datetime,
    ) -> bool:
        stmt = (
            update(MessagingParticipantModel)
            .where(
                MessagingParticipantModel.conversation_id == conversation_id.value,
                MessagingParticipantModel.user_id == user_id.value,
                MessagingParticipantModel.last_read_sequence < sequence,
            )
            .values(
                last_read_sequence=sequence,
                last_read_message_id=message_id.value,
                last_read_at=at,
            )
        )
        result = await self._session.execute(stmt)
        return cast(bool, getattr(result, "rowcount", 0) == 1)

    def _to_domain(self, model: MessagingMessageModel) -> Message:
        return Message(
            id=EntityId(model.id),
            conversation_id=EntityId(model.conversation_id),
            sender_id=EntityId(model.sender_id),
            sequence=model.sequence,
            content=MessageContent.create(model.content),
            client_message_id=ClientMessageId(model.client_message_id),
            created_at=model.created_at,
        )


class SqlAlchemyRestrictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, restriction: CommunicationRestriction) -> bool:
        stmt = insert(MessagingRestrictionModel).values(
            id=restriction.id.value,
            user_id=restriction.user_id.value,
            starts_at=restriction.starts_at,
            ends_at=restriction.ends_at,
            source_reference=restriction.source_reference.value,
            status=restriction.status,
            lifted_at=restriction.lifted_at,
            created_at=restriction.created_at or datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["source_reference"])

        result = await self._session.execute(stmt)
        await self._session.flush()
        return cast(int, getattr(result, "rowcount", 0)) > 0

    async def get_by_source_reference(self, source_reference: EntityId) -> CommunicationRestriction | None:
        stmt = select(MessagingRestrictionModel).where(MessagingRestrictionModel.source_reference == source_reference.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_active_for_user(self, user_id: EntityId, now: datetime | None = None) -> CommunicationRestriction | None:
        now = now or datetime.now(timezone.utc)
        stmt = select(MessagingRestrictionModel).where(
            and_(
                MessagingRestrictionModel.user_id == user_id.value,
                MessagingRestrictionModel.status == "ACTIVE",
                MessagingRestrictionModel.starts_at <= now,
                MessagingRestrictionModel.ends_at > now,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update(self, restriction: CommunicationRestriction) -> None:
        stmt = select(MessagingRestrictionModel).where(MessagingRestrictionModel.id == restriction.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.status = restriction.status
            model.lifted_at = restriction.lifted_at

    def _to_domain(self, model: MessagingRestrictionModel) -> CommunicationRestriction:
        return CommunicationRestriction(
            id=EntityId(model.id),
            user_id=EntityId(model.user_id),
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            source_reference=EntityId(model.source_reference),
            status=model.status,
            lifted_at=model.lifted_at,
            created_at=model.created_at,
        )
