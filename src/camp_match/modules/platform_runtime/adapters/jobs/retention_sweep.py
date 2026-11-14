"""Retention sweep job factory."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog

from camp_match.modules.identity.adapters.persistence.one_time_code_repository import (
    SqlAlchemyOneTimeCodeRepository,
)
from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository as MessagingOutboxRepository,
)
from camp_match.modules.messaging.adapters.ratelimit.postgres_rate_limiter import (
    PostgresRateLimiter,
)
from camp_match.modules.notification.adapters.persistence.inbox_repository import (
    SqlAlchemyInboxRepository as NotificationInboxRepository,
)
from camp_match.modules.notification.adapters.persistence.notification_repository import (
    SqlAlchemyNotificationRepository as NotificationRepository,
)
from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository as PlatformOutboxRepository,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

logger = structlog.get_logger()


def build_retention_sweep_job(
    session_factory: Any,
    session: Any = None,
    clock: Any = None,
    settings: Any = None,
    event_bus: Any = None,
) -> Any:
    if session is not None and (hasattr(session, "now") or not hasattr(session, "execute")):
        if clock is not None and hasattr(clock, "app_name"):
            settings = clock
        clock = session
    if clock is not None and hasattr(clock, "app_name") and settings is None:
        settings = clock
        clock = None

    if clock is None:
        from camp_match.platform.clock import get_clock
        clock = get_clock()
    if settings is None:
        from camp_match.config.settings import get_settings
        settings = get_settings()

    async def run() -> int:
        now = clock.now()
        batch_size = getattr(settings, "retention_batch_size", 500)

        platform_cutoff = now - timedelta(
            days=getattr(settings, "retention_platform_outbox_days", 7)
        )
        messaging_cutoff = now - timedelta(
            days=getattr(settings, "retention_messaging_outbox_days", 7)
        )
        notification_inbox_cutoff = now - timedelta(
            days=getattr(settings, "retention_notification_inbox_days", 14)
        )
        notification_read_cutoff = now - timedelta(
            days=getattr(settings, "retention_notification_read_days", 90)
        )
        rate_limit_cutoff = now - timedelta(
            hours=getattr(settings, "retention_rate_limit_hours", 24)
        )
        identity_codes_cutoff = now - timedelta(
            days=getattr(settings, "retention_identity_codes_days", 7)
        )

        async with session_factory() as db_session:
            uow = SqlAlchemyUnitOfWork(db_session)
            platform_repo = PlatformOutboxRepository(db_session)
            messaging_repo = MessagingOutboxRepository(db_session)
            inbox_repo = NotificationInboxRepository(db_session)
            notif_repo = NotificationRepository(db_session)
            identity_otc_repo = SqlAlchemyOneTimeCodeRepository(db_session)

            p1 = await platform_repo.purge_delivered(platform_cutoff, batch_size)
            p2 = await messaging_repo.purge_dispatched(messaging_cutoff, batch_size)
            p3 = await inbox_repo.purge_processed_or_rejected(
                notification_inbox_cutoff, batch_size
            )
            p4 = await notif_repo.purge_read_notifications(
                notification_read_cutoff, batch_size
            )
            p6 = await identity_otc_repo.purge_expired_or_inactive(
                identity_codes_cutoff, batch_size
            )

            await uow.commit()

        rate_limiter = PostgresRateLimiter(session_factory, clock)
        p5 = await rate_limiter.purge_old_windows(rate_limit_cutoff, batch_size)

        total_purged = p1 + p2 + p3 + p4 + p5 + p6

        logger.info(
            "retention_sweep_completed",
            platform_purged=p1,
            messaging_purged=p2,
            notification_inbox_purged=p3,
            notification_notifications_purged=p4,
            rate_limits_purged=p5,
            identity_codes_purged=p6,
            total=total_purged,
        )
        return total_purged

    return run
