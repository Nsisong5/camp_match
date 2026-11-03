from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import structlog
from fastapi import WebSocket

from camp_match.config.settings import get_settings
from camp_match.modules.messaging.adapters.api.ws_protocol import (
    AuthCommand,
    PingCommand,
    ReadAdvanceCommand,
    SendMessageCommand,
    SubscribeCommand,
    UnsubscribeCommand,
    frame_auth_expired,
    frame_auth_ok,
    frame_error,
    frame_message_accepted,
    frame_pong,
    frame_read_accepted,
    frame_subscribed,
    frame_unsubscribed,
    parse_client_command,
)
from camp_match.modules.messaging.adapters.persistence.repository import (
    SqlAlchemyRestrictionRepository,
)
from camp_match.modules.messaging.adapters.realtime.connection_manager import Connection
from camp_match.modules.messaging.application.ports.inbound import (
    AuthorizeConnectionRequest,
    AuthorizeSubscriptionRequest,
    MarkConversationReadRequest,
    SendMessageRequest,
)
from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard
from camp_match.modules.messaging.application.use_cases.authorize_connection import (
    AuthorizeConnectionUseCase,
)
from camp_match.modules.messaging.application.use_cases.authorize_subscription import (
    AuthorizeSubscriptionUseCase,
)
from camp_match.modules.messaging.application.use_cases.mark_conversation_read import (
    MarkConversationReadUseCase,
)
from camp_match.modules.messaging.application.use_cases.send_message import SendMessageUseCase
from camp_match.platform.clock import get_clock
from camp_match.platform.security.authentication import decode_access_token_string
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


async def handle_websocket(
    websocket: WebSocket,
    connection_manager: Any,
    db_session_factory: Any,
    rate_limiter: Any,
) -> None:
    settings = get_settings()
    clock = get_clock()
    client_host = websocket.client.host if websocket.client else "unknown"

    # 1. Connect rate limit check
    connect_key = f"ws_connect:{client_host}"
    rl_res = await rate_limiter.check(connect_key, settings.messaging_ws_connect_rate_limit, 60)
    if not rl_res.allowed:
        await websocket.close(code=4429, reason="Connect rate limit exceeded.")
        return

    await websocket.accept()

    connection: Connection | None = None
    protocol_violations = 0

    try:
        # 2. Wait for auth frame within timeout
        try:
            async with asyncio.timeout(settings.messaging_ws_auth_timeout_seconds):
                raw_data = await websocket.receive_json()
        except TimeoutError:
            await websocket.close(code=4401, reason="Auth timeout.")
            return
        except Exception:
            await websocket.close(code=4401, reason="Invalid initial frame.")
            return

        try:
            cmd = parse_client_command(raw_data)
        except Exception:
            await websocket.close(code=4401, reason="Invalid auth command format.")
            return

        if not isinstance(cmd, AuthCommand):
            await websocket.close(code=4401, reason="First frame must be auth.")
            return

        # 3. Decode token
        try:
            identity_id = await decode_access_token_string(cmd.token)
        except Exception:
            await websocket.close(code=4401, reason="Invalid authentication token.")
            return

        # 4. Authorize connection using DB session
        async with db_session_factory() as session:
            from camp_match.modules.identity.adapters.persistence.repository import (
                SqlAlchemyIdentityRepository,
            )
            from camp_match.modules.messaging.adapters.restriction.identity_restriction_provider import (
                IdentityBackedRestrictionProvider,
            )
            from camp_match.modules.messaging.adapters.security.authorization import (
                InProcessAuthorizationService,
            )
            from camp_match.modules.profile.adapters.persistence.repository import (
                SqlAlchemyProfileRepository,
            )
            from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
                GetCurrentUserProfileUseCase,
            )
            from camp_match.modules.security.adapters.persistence.repository import (
                SqlAlchemyRoleRepository,
            )
            from camp_match.modules.security.adapters.profile.profile_provider import (
                InProcessProfileProvider as SecurityProfileProvider,
            )
            from camp_match.modules.security.application.use_cases.authorize_action import (
                AuthorizeActionUseCase,
            )

            account_repo = SqlAlchemyIdentityRepository(session)
            restriction_repo = SqlAlchemyRestrictionRepository(session)
            restriction_prov = IdentityBackedRestrictionProvider(account_repo, restriction_repo)
            role_repo = SqlAlchemyRoleRepository(session)
            profile_repo = SqlAlchemyProfileRepository(session)
            profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
            sec_profile_provider = SecurityProfileProvider(profile_use_case)
            authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
            auth_service = InProcessAuthorizationService(authorize_uc)

            auth_conn_uc = AuthorizeConnectionUseCase(restriction_prov, auth_service)
            try:
                await auth_conn_uc.execute(AuthorizeConnectionRequest(actor_id=identity_id))
            except Exception:
                await websocket.close(code=4403, reason="Connection not permitted.")
                return

        # 5. Enforce max connections per user
        current_user_conns = await connection_manager.count_user_connections(identity_id.value)
        if current_user_conns >= settings.messaging_ws_max_connections_per_user:
            await websocket.close(code=4429, reason="Max connections per user exceeded.")
            return

        now = clock.now()
        authenticated_until = now + timedelta(seconds=settings.messaging_ws_auth_ttl_seconds)

        connection = Connection(
            websocket=websocket,
            user_id=identity_id.value,
            authenticated_until=authenticated_until,
        )
        await connection_manager.register(connection)
        logger.info("ws_connection_accepted", user_id=str(identity_id), connection_id=str(connection.connection_id))

        await websocket.send_json(frame_auth_ok())

        # 6. Main receive loop
        while True:
            now = clock.now()
            is_auth_expired = connection.authenticated_until and now >= connection.authenticated_until

            try:
                async with asyncio.timeout(settings.messaging_ws_idle_timeout_seconds):
                    raw_data = await websocket.receive_json()
            except TimeoutError:
                await websocket.close(code=4408, reason="Idle timeout.")
                break
            except Exception:
                # Connection closed or error
                break

            try:
                cmd = parse_client_command(raw_data)
            except Exception:
                protocol_violations += 1
                if protocol_violations > 5:
                    await websocket.close(code=4400, reason="Too many protocol violations.")
                    break
                await websocket.send_json(frame_error("invalid_command", "Invalid command format."))
                continue

            if isinstance(cmd, PingCommand):
                await websocket.send_json(frame_pong())
                continue

            if isinstance(cmd, AuthCommand):
                try:
                    new_identity = await decode_access_token_string(cmd.token)
                    if new_identity.value != connection.user_id:
                        await websocket.close(code=4401, reason="Token user mismatch on re-auth.")
                        break
                    connection.authenticated_until = clock.now() + timedelta(seconds=settings.messaging_ws_auth_ttl_seconds)
                    await websocket.send_json(frame_auth_ok())
                    continue
                except Exception:
                    await websocket.close(code=4401, reason="Invalid re-auth token.")
                    break

            if is_auth_expired:
                await websocket.send_json(frame_auth_expired())
                await websocket.close(code=4401, reason="Auth expired.")
                break

            # Handle messaging commands
            async with db_session_factory() as session:
                from camp_match.modules.booking.adapters.persistence.repository import (
                    SqlAlchemyBookingRepository,
                )
                from camp_match.modules.housing.adapters.persistence.repository import (
                    SqlAlchemyListingRepository,
                    SqlAlchemyPropertyRepository,
                )
                from camp_match.modules.messaging.adapters.booking.booking_provider import (
                    InProcessBookingProvider,
                )
                from camp_match.modules.messaging.adapters.events.null_dispatcher import (
                    NullMessageEventDispatcher,
                )
                from camp_match.modules.messaging.adapters.listing.listing_provider import (
                    InProcessListingProvider,
                )
                from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
                    SqlAlchemyOutboxRepository,
                )
                from camp_match.modules.messaging.adapters.persistence.repository import (
                    SqlAlchemyConversationRepository,
                    SqlAlchemyMessageRepository,
                )
                from camp_match.modules.messaging.adapters.profile.profile_provider import (
                    InProcessProfileProvider,
                )
                from camp_match.modules.profile.adapters.persistence.repository import (
                    SqlAlchemyProfileRepository,
                )
                from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

                conv_repo = SqlAlchemyConversationRepository(session)
                message_repo = SqlAlchemyMessageRepository(session)
                outbox_repo = SqlAlchemyOutboxRepository(session)
                account_repo = SqlAlchemyIdentityRepository(session)
                restriction_repo = SqlAlchemyRestrictionRepository(session)
                restriction_prov = IdentityBackedRestrictionProvider(account_repo, restriction_repo)
                role_repo = SqlAlchemyRoleRepository(session)
                profile_repo = SqlAlchemyProfileRepository(session)
                profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
                sec_profile_provider = SecurityProfileProvider(profile_use_case)
                authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
                auth_service = InProcessAuthorizationService(authorize_uc)

                guard = ParticipantGuard(conv_repo, restriction_prov, auth_service)

                if isinstance(cmd, SubscribeCommand):
                    if len(connection.subscriptions) >= settings.messaging_ws_max_subscriptions_per_connection:
                        await websocket.send_json(frame_error("subscription_limit", "Maximum subscriptions reached."))
                        continue
                    auth_sub_uc = AuthorizeSubscriptionUseCase(guard)
                    try:
                        conv = await auth_sub_uc.execute(
                            AuthorizeSubscriptionRequest(actor_id=identity_id, conversation_id=EntityId.from_string(cmd.conversation_id))
                        )
                        await connection_manager.subscribe(connection.connection_id, conv.id.value)
                        await websocket.send_json(frame_subscribed(cmd.conversation_id))
                    except Exception as e:
                        from camp_match.modules.messaging.application.errors import (
                            ConversationNotFound,
                        )
                        if isinstance(e, ConversationNotFound):
                            await websocket.send_json(frame_error("conversation_not_found", "Conversation not found."))
                        else:
                            await websocket.send_json(frame_error("forbidden", str(e)))

                elif isinstance(cmd, UnsubscribeCommand):
                    await connection_manager.unsubscribe(connection.connection_id, UUID(cmd.conversation_id))
                    await websocket.send_json(frame_unsubscribed(cmd.conversation_id))

                elif isinstance(cmd, SendMessageCommand):
                    # Command rate limit check
                    cmd_rl = await rate_limiter.check(
                        f"ws_cmd:{identity_id}",
                        settings.messaging_ws_command_rate_limit,
                        60,
                    )
                    if not cmd_rl.allowed:
                        await websocket.send_json(frame_error("rate_limit_exceeded", "Command rate limit exceeded."))
                        continue

                    listing_repo = SqlAlchemyListingRepository(session)
                    property_repo = SqlAlchemyPropertyRepository(session)
                    listing_prov = InProcessListingProvider(listing_repo, property_repo)
                    booking_repo = SqlAlchemyBookingRepository(session)
                    booking_prov = InProcessBookingProvider(booking_repo, listing_prov, auth_service)
                    profile_prov = InProcessProfileProvider(profile_repo)

                    from camp_match.modules.messaging.adapters.realtime.factory import (
                        create_realtime_gateway,
                    )
                    gateway = create_realtime_gateway(settings, connection_manager)
                    dispatcher = NullMessageEventDispatcher()
                    uow = SqlAlchemyUnitOfWork(session)

                    send_uc = SendMessageUseCase(
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

                    try:
                        res = await send_uc.execute(
                            SendMessageRequest(
                                actor_id=identity_id,
                                conversation_id=EntityId.from_string(cmd.conversation_id),
                                client_message_id=cmd.client_message_id,
                                content=cmd.content,
                            )
                        )
                        msg_payload = {
                            "id": str(res.message.id),
                            "conversation_id": str(res.message.conversation_id),
                            "sender_id": str(res.message.sender_id),
                            "content": res.message.content,
                            "sequence": res.message.sequence,
                            "cursor": res.message.cursor,
                            "created_at": res.message.created_at.isoformat(),
                            "client_message_id": res.message.client_message_id,
                        }
                        await websocket.send_json(frame_message_accepted(cmd.client_message_id, msg_payload, res.replayed))
                    except Exception as e:
                        from camp_match.shared_kernel.application.errors import ApplicationError
                        if isinstance(e, ApplicationError):
                            code = e.code or "application_error"
                            await websocket.send_json(frame_error(code, str(e)))
                        else:
                            logger.error("ws_send_message_error", error=str(e), user_id=str(identity_id))
                            await websocket.send_json(frame_error("internal_error", "An unexpected error occurred."))

                elif isinstance(cmd, ReadAdvanceCommand):
                    read_uc = MarkConversationReadUseCase(
                        participant_guard=guard,
                        conversation_repo=conv_repo,
                        message_repo=message_repo,
                        uow=SqlAlchemyUnitOfWork(session),
                        clock=clock,
                    )
                    try:
                        res = await read_uc.execute(
                            MarkConversationReadRequest(
                                actor_id=identity_id,
                                conversation_id=EntityId.from_string(cmd.conversation_id),
                                up_to_message_id=EntityId.from_string(cmd.up_to_message_id),
                            )
                        )
                        await websocket.send_json(
                            frame_read_accepted(
                                str(res.conversation_id),
                                str(res.last_read_message_id) if res.last_read_message_id else None,
                                res.unread_count,
                            )
                        )
                    except Exception as e:
                        from camp_match.shared_kernel.application.errors import ApplicationError
                        if isinstance(e, ApplicationError):
                            code = e.code or "application_error"
                            await websocket.send_json(frame_error(code, str(e)))
                        else:
                            await websocket.send_json(frame_error("internal_error", "An unexpected error occurred."))

    finally:
        if connection:
            await connection_manager.unregister(connection)
            logger.info("ws_connection_closed", user_id=str(connection.user_id), connection_id=str(connection.connection_id))
