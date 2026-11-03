from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

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
from camp_match.modules.profile.adapters.api.router import router as profile_router
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

    if settings.app_env in ("local", "test") and getattr(settings, "messaging_debug_failing_subscriber", False):
        from camp_match.modules.messaging.domain.events import MessageCreated
        async def failing_subscriber(event: object) -> None:
            raise RuntimeError("Intentional failing subscriber for debug.")
        event_bus.subscribe(MessageCreated, failing_subscriber)
    yield
    await connection_manager.close_all()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Camp Match API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(university_router)
    app.include_router(housing_router)
    app.include_router(search_router)
    app.include_router(media_router)
    app.include_router(verification_router)
    app.include_router(verification_status_router)
    app.include_router(booking_router)
    app.include_router(payment_router)
    app.include_router(payment_webhook_router)
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
        app.include_router(payment_mock_router)

    @app.get("/health", tags=["infrastructure"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
