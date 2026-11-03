from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from camp_match.modules.messaging.adapters.api import dependencies, schemas
from camp_match.modules.messaging.application.ports.inbound import (
    ConversationView,
    FindOrCreateConversationRequest,
    GetConversationRequest,
    GetMessageHistoryRequest,
    ListConversationsRequest,
    MarkConversationReadRequest,
    MessageView,
    SendMessageRequest,
)
from camp_match.modules.messaging.application.use_cases.find_or_create_conversation import (
    FindOrCreateConversationUseCase,
)
from camp_match.modules.messaging.application.use_cases.get_conversation import (
    GetConversationUseCase,
)
from camp_match.modules.messaging.application.use_cases.get_message_history import (
    GetMessageHistoryUseCase,
)
from camp_match.modules.messaging.application.use_cases.list_conversations import (
    ListConversationsUseCase,
)
from camp_match.modules.messaging.application.use_cases.mark_conversation_read import (
    MarkConversationReadUseCase,
)
from camp_match.modules.messaging.application.use_cases.send_message import SendMessageUseCase
from camp_match.platform.security.authentication import get_current_identity_id
from camp_match.shared_kernel.application.pagination import PageRequest
from camp_match.shared_kernel.domain.identifiers import EntityId

router = APIRouter(prefix="/api/v1/messaging", tags=["Messaging"])


def _build_conversation_view_schema(view: ConversationView) -> schemas.ConversationViewSchema:
    return schemas.ConversationViewSchema(
        id=view.id.value,
        context_type=view.context_type,
        listing_id=view.listing_id.value if view.listing_id else None,
        booking_id=view.booking_id.value if view.booking_id else None,
        counterpart=schemas.ParticipantViewSchema(
            user_id=view.counterpart.user_id.value,
            profile_id=view.counterpart.profile_id.value if view.counterpart.profile_id else None,
            display_name=view.counterpart.display_name,
            profile_type=view.counterpart.profile_type,
        ),
        last_message=schemas.LastMessageViewSchema(
            id=view.last_message.id.value,
            sender_id=view.last_message.sender_id.value,
            preview=view.last_message.preview,
            sequence=view.last_message.sequence,
            created_at=view.last_message.created_at,
        ) if view.last_message else None,
        last_activity_at=view.last_activity_at,
        unread_count=view.unread_count,
        last_read_message_id=view.last_read_message_id.value if view.last_read_message_id else None,
        created_at=view.created_at,
    )


def _build_message_view_schema(msg: MessageView) -> schemas.MessageViewSchema:
    return schemas.MessageViewSchema(
        id=msg.id.value,
        conversation_id=msg.conversation_id.value,
        sender_id=msg.sender_id.value,
        content=msg.content,
        sequence=msg.sequence,
        cursor=msg.cursor,
        created_at=msg.created_at,
        client_message_id=msg.client_message_id,
    )


@router.post("/conversations", response_model=schemas.FindOrCreateResultSchema)
async def find_or_create_conversation(
    request: schemas.FindOrCreateConversationSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[FindOrCreateConversationUseCase, Depends(dependencies.get_find_or_create_use_case)],
    response: Response,
) -> schemas.FindOrCreateResultSchema:
    res = await use_case.execute(
        FindOrCreateConversationRequest(
            actor_id=identity_id,
            context_type=request.context_type,
            listing_id=EntityId(request.listing_id) if request.listing_id else None,
            booking_id=EntityId(request.booking_id) if request.booking_id else None,
        )
    )
    response.status_code = status.HTTP_201_CREATED if res.created else status.HTTP_200_OK
    conv_schema = _build_conversation_view_schema(res.conversation)
    return schemas.FindOrCreateResultSchema(
        conversation=conv_schema,
        created=res.created,
    )


@router.get("/conversations", response_model=schemas.PageSchema[schemas.ConversationViewSchema])
async def list_conversations(
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[ListConversationsUseCase, Depends(dependencies.get_list_conversations_use_case)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> schemas.PageSchema[schemas.ConversationViewSchema]:
    page_result = await use_case.execute(
        ListConversationsRequest(
            actor_id=identity_id,
            page=PageRequest(page=page, page_size=page_size),
        )
    )
    items = [_build_conversation_view_schema(item) for item in page_result.items]
    return schemas.PageSchema(
        items=items,
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationViewSchema)
async def get_conversation(
    conversation_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetConversationUseCase, Depends(dependencies.get_get_conversation_use_case)],
) -> schemas.ConversationViewSchema:
    view = await use_case.execute(
        GetConversationRequest(
            actor_id=identity_id,
            conversation_id=EntityId(conversation_id),
        )
    )
    return _build_conversation_view_schema(view)


@router.get("/conversations/{conversation_id}/messages", response_model=schemas.HistoryPageSchema)
async def get_message_history(
    conversation_id: UUID,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[GetMessageHistoryUseCase, Depends(dependencies.get_get_message_history_use_case)],
    limit: int = Query(30, ge=1, le=100),
    before: str | None = None,
    after: str | None = None,
) -> schemas.HistoryPageSchema:
    page = await use_case.execute(
        GetMessageHistoryRequest(
            actor_id=identity_id,
            conversation_id=EntityId(conversation_id),
            limit=limit,
            before=before,
            after=after,
        )
    )
    items = [_build_message_view_schema(item) for item in page.items]
    return schemas.HistoryPageSchema(
        items=items,
        has_older=page.has_older,
        has_newer=page.has_newer,
        older_cursor=page.older_cursor,
        newer_cursor=page.newer_cursor,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=schemas.SendMessageResultSchema)
async def send_message(
    conversation_id: UUID,
    request: schemas.SendMessageSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[SendMessageUseCase, Depends(dependencies.get_send_message_use_case)],
    response: Response,
) -> schemas.SendMessageResultSchema:
    res = await use_case.execute(
        SendMessageRequest(
            actor_id=identity_id,
            conversation_id=EntityId(conversation_id),
            client_message_id=request.client_message_id,
            content=request.content,
        )
    )
    response.status_code = status.HTTP_200_OK if res.replayed else status.HTTP_201_CREATED
    msg_schema = _build_message_view_schema(res.message)
    return schemas.SendMessageResultSchema(
        message=msg_schema,
        replayed=res.replayed,
    )


@router.post("/conversations/{conversation_id}/read", response_model=schemas.ReadResultSchema)
async def mark_conversation_read(
    conversation_id: UUID,
    request: schemas.MarkReadSchema,
    identity_id: Annotated[EntityId, Depends(get_current_identity_id)],
    use_case: Annotated[MarkConversationReadUseCase, Depends(dependencies.get_mark_conversation_read_use_case)],
) -> schemas.ReadResultSchema:
    res = await use_case.execute(
        MarkConversationReadRequest(
            actor_id=identity_id,
            conversation_id=EntityId(conversation_id),
            up_to_message_id=EntityId(request.up_to_message_id),
        )
    )
    return schemas.ReadResultSchema(
        conversation_id=res.conversation_id.value,
        last_read_message_id=res.last_read_message_id.value if res.last_read_message_id else None,
        unread_count=res.unread_count,
    )
