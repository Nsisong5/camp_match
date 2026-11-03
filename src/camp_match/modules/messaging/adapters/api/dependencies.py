from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import get_settings
from camp_match.modules.booking.adapters.persistence.repository import SqlAlchemyBookingRepository
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
)
from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
from camp_match.modules.messaging.adapters.booking.booking_provider import InProcessBookingProvider
from camp_match.modules.messaging.adapters.events.null_dispatcher import NullMessageEventDispatcher
from camp_match.modules.messaging.adapters.listing.listing_provider import InProcessListingProvider
from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.modules.messaging.adapters.persistence.repository import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyRestrictionRepository,
)
from camp_match.modules.messaging.adapters.profile.profile_provider import InProcessProfileProvider
from camp_match.modules.messaging.application.use_cases.restriction_management import (
    LiftCommunicationRestrictionUseCase,
    RestrictCommunicationUseCase,
)
from camp_match.modules.messaging.adapters.ratelimit.in_memory_rate_limiter import (
    InMemoryRateLimiter,
)
from camp_match.modules.messaging.adapters.realtime.null_gateway import NullRealtimeGateway
from camp_match.modules.messaging.adapters.restriction.identity_restriction_provider import (
    IdentityBackedRestrictionProvider,
)
from camp_match.modules.messaging.adapters.security.authorization import (
    InProcessAuthorizationService,
)
from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard
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
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


def get_rate_limiter(request: Request) -> InMemoryRateLimiter:
    if not hasattr(request.app.state, "rate_limiter"):
        request.app.state.rate_limiter = InMemoryRateLimiter()
    return request.app.state.rate_limiter


def get_authorization_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> InProcessAuthorizationService:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizationService(authorize_uc)


def get_restriction_provider(session: Annotated[AsyncSession, Depends(get_db_session)]) -> IdentityBackedRestrictionProvider:
    account_repo = SqlAlchemyIdentityRepository(session)
    restriction_repo = SqlAlchemyRestrictionRepository(session)
    return IdentityBackedRestrictionProvider(account_repo, restriction_repo)


def get_participant_guard(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    restriction_prov: Annotated[IdentityBackedRestrictionProvider, Depends(get_restriction_provider)],
) -> ParticipantGuard:
    conv_repo = SqlAlchemyConversationRepository(session)
    message_repo = SqlAlchemyMessageRepository(session)
    return ParticipantGuard(conv_repo, restriction_prov, auth_service, message_repo)


def get_restrict_communication_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> RestrictCommunicationUseCase:
    restriction_repo = SqlAlchemyRestrictionRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    return RestrictCommunicationUseCase(restriction_repo, auth_service, uow)


def get_lift_communication_restriction_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
) -> LiftCommunicationRestrictionUseCase:
    restriction_repo = SqlAlchemyRestrictionRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    return LiftCommunicationRestrictionUseCase(restriction_repo, auth_service, uow)


def get_find_or_create_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    restriction_prov: Annotated[IdentityBackedRestrictionProvider, Depends(get_restriction_provider)],
) -> FindOrCreateConversationUseCase:
    conv_repo = SqlAlchemyConversationRepository(session)
    message_repo = SqlAlchemyMessageRepository(session)
    listing_repo = SqlAlchemyListingRepository(session)
    property_repo = SqlAlchemyPropertyRepository(session)
    listing_prov = InProcessListingProvider(listing_repo, property_repo)

    booking_repo = SqlAlchemyBookingRepository(session)
    booking_prov = InProcessBookingProvider(booking_repo, listing_prov, auth_service)

    profile_repo = SqlAlchemyProfileRepository(session)
    profile_prov = InProcessProfileProvider(profile_repo)

    rate_limiter = get_rate_limiter(request)
    uow = SqlAlchemyUnitOfWork(session)
    clock = get_clock()
    settings = get_settings()

    return FindOrCreateConversationUseCase(
        conversation_repo=conv_repo,
        message_repo=message_repo,
        listing_provider=listing_prov,
        booking_provider=booking_prov,
        profile_provider=profile_prov,
        restriction_provider=restriction_prov,
        rate_limiter=rate_limiter,
        authorization_service=auth_service,
        uow=uow,
        clock=clock,
        settings=settings,
    )


def get_list_conversations_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[InProcessAuthorizationService, Depends(get_authorization_service)],
    restriction_prov: Annotated[IdentityBackedRestrictionProvider, Depends(get_restriction_provider)],
) -> ListConversationsUseCase:
    conv_repo = SqlAlchemyConversationRepository(session)
    message_repo = SqlAlchemyMessageRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_prov = InProcessProfileProvider(profile_repo)

    return ListConversationsUseCase(
        conversation_repo=conv_repo,
        message_repo=message_repo,
        profile_provider=profile_prov,
        restriction_provider=restriction_prov,
        authorization_service=auth_service,
    )


def get_get_conversation_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    guard: Annotated[ParticipantGuard, Depends(get_participant_guard)],
) -> GetConversationUseCase:
    conv_repo = SqlAlchemyConversationRepository(session)
    message_repo = SqlAlchemyMessageRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_prov = InProcessProfileProvider(profile_repo)

    return GetConversationUseCase(
        participant_guard=guard,
        conversation_repo=conv_repo,
        message_repo=message_repo,
        profile_provider=profile_prov,
    )


def get_send_message_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    guard: Annotated[ParticipantGuard, Depends(get_participant_guard)],
    request: Request,
    restriction_prov: Annotated[IdentityBackedRestrictionProvider, Depends(get_restriction_provider)],
) -> SendMessageUseCase:
    message_repo = SqlAlchemyMessageRepository(session)
    outbox_repo = SqlAlchemyOutboxRepository(session)
    rate_limiter = get_rate_limiter(request)
    gateway = NullRealtimeGateway()
    dispatcher = NullMessageEventDispatcher()
    uow = SqlAlchemyUnitOfWork(session)
    clock = get_clock()
    settings = get_settings()

    return SendMessageUseCase(
        participant_guard=guard,
        message_repo=message_repo,
        outbox_repo=outbox_repo,
        restriction_provider=restriction_prov,
        rate_limiter=rate_limiter,
        realtime_gateway=gateway,
        message_event_dispatcher=dispatcher,
        uow=uow,
        clock=clock,
        settings=settings,
    )


def get_get_message_history_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    guard: Annotated[ParticipantGuard, Depends(get_participant_guard)],
) -> GetMessageHistoryUseCase:
    message_repo = SqlAlchemyMessageRepository(session)
    settings = get_settings()
    return GetMessageHistoryUseCase(participant_guard=guard, message_repo=message_repo, settings=settings)


def get_mark_conversation_read_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    guard: Annotated[ParticipantGuard, Depends(get_participant_guard)],
) -> MarkConversationReadUseCase:
    conv_repo = SqlAlchemyConversationRepository(session)
    message_repo = SqlAlchemyMessageRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    clock = get_clock()
    return MarkConversationReadUseCase(
        participant_guard=guard,
        conversation_repo=conv_repo,
        message_repo=message_repo,
        uow=uow,
        clock=clock,
    )
