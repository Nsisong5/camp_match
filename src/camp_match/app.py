from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from camp_match.config.settings import get_settings
from camp_match.modules.admin_operations.adapters.api.router import router as admin_router
from camp_match.modules.booking.adapters.api.router import router as booking_router
from camp_match.modules.housing.adapters.api.router import router as housing_router
from camp_match.modules.identity.adapters.api.router import router as auth_router
from camp_match.modules.media.adapters.api.router import router as media_router
from camp_match.modules.messaging.adapters.api.router import router as messaging_router
from camp_match.modules.messaging.adapters.api.ws_router import router as messaging_ws_router
from camp_match.modules.messaging.adapters.ratelimit.in_memory_rate_limiter import (
    InMemoryRateLimiter,
)
from camp_match.modules.messaging.adapters.realtime.connection_manager import ConnectionManager
from camp_match.modules.notification.adapters.api.router import router as notification_router
from camp_match.modules.payment.adapters.api.router import router as payment_router
from camp_match.modules.payment.adapters.api.webhook_router import router as payment_webhook_router
from camp_match.modules.payment.adapters.api.review_router import router as payment_review_router
from camp_match.modules.profile.adapters.api.router import router as profile_router
from camp_match.modules.saved_listings.adapters.api.router import router as saved_listings_router
from camp_match.modules.search.adapters.api.router import router as search_router
from camp_match.modules.trust_safety.adapters.api.reporter_router import (
    router as safety_reporter_router,
)
from camp_match.modules.trust_safety.adapters.api.review_router import (
    router as safety_review_router,
)
from camp_match.modules.university_location.adapters.api.router import router as university_router
from camp_match.modules.verification.adapters.api.router import (
    public_router as verification_status_router,
)
from camp_match.modules.verification.adapters.api.router import (
    router as verification_router,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.errors.http_error_handlers import register_error_handlers
from camp_match.platform.event_bus import build_event_bus
from camp_match.platform.logging.middleware import RequestIDMiddleware
from camp_match.platform.logging.setup import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings)
    structlog.get_logger().info("messaging_realtime_backend=in_memory single_process=true")
    engine = create_engine(settings)
    app.state.db_engine = engine
    session_factory = create_session_factory(engine)
    app.state.db_session_factory = session_factory
    app.state.rate_limiter = InMemoryRateLimiter()
    connection_manager = ConnectionManager()
    app.state.connection_manager = connection_manager
    clock = get_clock()
    event_bus = build_event_bus(session_factory, clock, settings)
    app.state.event_bus = event_bus

    from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
        SqlAlchemyOutboxRepository,
    )
    from camp_match.modules.platform_runtime.adapters.nudge.outbox_nudge_listener import (
        OutboxNudgeListener,
    )
    from camp_match.modules.platform_runtime.adapters.registry.setup import (
        create_default_event_registry,
    )
    from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import (
        RelayOutboxBatchUseCase,
    )
    from camp_match.platform.db.unit_of_work import configure_unit_of_work_outbox

    registry = create_default_event_registry()
    relay_uc = RelayOutboxBatchUseCase(
        session_factory, SqlAlchemyOutboxRepository, registry, event_bus, clock, settings
    )
    nudge_listener = OutboxNudgeListener(relay_uc, settings)
    configure_unit_of_work_outbox(registry, nudge_listener, clock)

    if settings.app_env in ("local", "test") and getattr(settings, "messaging_debug_failing_subscriber", False):
        from camp_match.modules.messaging.domain.events import MessageCreated
        async def failing_subscriber(event: object) -> None:
            raise RuntimeError("Intentional failing subscriber for debug.")
        event_bus.subscribe(MessageCreated, failing_subscriber)

    listener_task = None
    if settings.messaging_realtime_backend == "postgres_notify":
        from camp_match.modules.messaging.adapters.realtime.postgres_notify_listener import run_postgres_notify_listener
        listener_task = asyncio.create_task(
            run_postgres_notify_listener(settings.database_url, session_factory, connection_manager, settings)
        )
        app.state.postgres_notify_listener_task = listener_task

    yield

    if listener_task:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

    await connection_manager.close_all()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Camp Match API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "Accept",
            "Origin",
            "X-Requested-With",
        ],
    )
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(university_router)
    app.include_router(housing_router)
    app.include_router(search_router)
    app.include_router(saved_listings_router)
    app.include_router(media_router)
    app.include_router(verification_router)
    app.include_router(verification_status_router)
    app.include_router(booking_router)
    app.include_router(payment_router)
    app.include_router(payment_webhook_router)
    app.include_router(payment_review_router)
    app.include_router(messaging_router)
    app.include_router(messaging_ws_router)
    app.include_router(notification_router)
    app.include_router(admin_router)
    app.include_router(safety_reporter_router)
    app.include_router(safety_review_router)

    settings = get_settings()
    if settings.app_env in ("local", "test"):
        from camp_match.modules.payment.adapters.provider.mock.mock_control_router import (
            router as payment_mock_router,
        )
        from camp_match.modules.identity.adapters.email.dev_mailbox_router import (
            router as dev_mailbox_router,
        )
        from camp_match.modules.identity.adapters.google.mock_minter_router import (
            router as mock_google_router,
        )
        app.include_router(payment_mock_router)
        app.include_router(dev_mailbox_router)
        app.include_router(mock_google_router)

    @app.get("/health", tags=["infrastructure"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
