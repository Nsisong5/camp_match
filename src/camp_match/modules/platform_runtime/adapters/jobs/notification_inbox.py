from __future__ import annotations

from typing import Any

from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyPropertyRepository,
)
from camp_match.modules.notification.adapters.housing.property_owner_provider import (
    SqlAlchemyPropertyOwnerProvider,
)
from camp_match.modules.notification.adapters.persistence.inbox_repository import (
    SqlAlchemyInboxRepository,
)
from camp_match.modules.notification.adapters.persistence.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from camp_match.modules.notification.application.ports.inbound import (
    ProcessPendingInboxRequest,
)
from camp_match.modules.notification.application.use_cases.process_inbox_event import (
    ProcessInboxEventUseCase,
)
from camp_match.modules.notification.application.use_cases.process_pending_inbox import (
    ProcessPendingInboxUseCase,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


def build_notification_inbox_job(
    session_factory: Any,
    session: Any = None,
    clock: Any = None,
    settings: Any = None,
    event_bus: Any = None,
) -> Any:
    if clock is None and settings is None and session is not None and hasattr(session, "now"):
        clock = session
        from camp_match.config.settings import get_settings
        settings = get_settings()
    elif clock is None and settings is not None and session is not None and hasattr(session, "now"):
        clock = session

    if clock is None:
        from camp_match.platform.clock import get_clock
        clock = get_clock()
    if settings is None:
        from camp_match.config.settings import get_settings
        settings = get_settings()

    async def run() -> None:
        async with session_factory() as db_session:
            inbox_repo = SqlAlchemyInboxRepository(db_session)
            notification_repo = SqlAlchemyNotificationRepository(db_session)
            property_repo = SqlAlchemyPropertyRepository(db_session)
            property_owner_provider = SqlAlchemyPropertyOwnerProvider(property_repo)
            uow = SqlAlchemyUnitOfWork(db_session)

            process_event_uc = ProcessInboxEventUseCase(
                inbox_repo=inbox_repo,
                notification_repo=notification_repo,
                property_owner_provider=property_owner_provider,
                uow=uow,
                clock=clock,
                max_attempts=settings.notification_inbox_max_attempts,
                backoff_base=settings.notification_inbox_backoff_base_seconds,
                backoff_cap=settings.notification_inbox_backoff_cap_seconds,
                debug_fail=getattr(
                    settings, "notification_debug_fail_processing", False
                ),
            )
            processor = ProcessPendingInboxUseCase(
                inbox_repo=inbox_repo,
                process_event_use_case=process_event_uc,
                clock=clock,
            )
            await processor.execute(
                ProcessPendingInboxRequest(
                    limit=settings.notification_worker_batch_size
                )
            )

    return run
