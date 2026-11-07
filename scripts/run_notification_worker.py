#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio

from camp_match.config.settings import get_settings
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
    GetInboxStatsRequest,
    ProcessPendingInboxRequest,
    RequeueDeadEventsRequest,
)
from camp_match.modules.notification.application.use_cases.get_inbox_stats import (
    GetInboxStatsUseCase,
)
from camp_match.modules.notification.application.use_cases.process_inbox_event import (
    ProcessInboxEventUseCase,
)
from camp_match.modules.notification.application.use_cases.process_pending_inbox import (
    ProcessPendingInboxUseCase,
)
from camp_match.modules.notification.application.use_cases.requeue_dead_events import (
    RequeueDeadEventsUseCase,
)
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyPropertyRepository,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


async def main() -> None:
    parser = argparse.ArgumentParser(description="Notification Worker Script")
    parser.add_argument("--stats", action="store_true", help="Print inbox stats")
    parser.add_argument("--requeue-dead", action="store_true", help="Requeue dead inbox events")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    clock = get_clock()

    async with session_factory() as session:
        inbox_repo = SqlAlchemyInboxRepository(session)
        notification_repo = SqlAlchemyNotificationRepository(session)
        property_repo = SqlAlchemyPropertyRepository(session)
        property_owner_provider = SqlAlchemyPropertyOwnerProvider(property_repo)
        uow = SqlAlchemyUnitOfWork(session)

        if args.stats:
            stats_uc = GetInboxStatsUseCase(inbox_repo)
            stats = await stats_uc.execute(GetInboxStatsRequest())
            print(f"Inbox Stats: {stats}")
        elif args.requeue_dead:
            requeue_uc = RequeueDeadEventsUseCase(inbox_repo, uow, clock, settings)
            count = await requeue_uc.execute(RequeueDeadEventsRequest())
            print(f"Requeued dead notification events: {count}")
        else:
            process_event_uc = ProcessInboxEventUseCase(
                inbox_repo=inbox_repo,
                notification_repo=notification_repo,
                property_owner_provider=property_owner_provider,
                uow=uow,
                clock=clock,
                max_attempts=settings.notification_inbox_max_attempts,
                backoff_base=settings.notification_inbox_backoff_base_seconds,
                backoff_cap=settings.notification_inbox_backoff_cap_seconds,
                debug_fail=getattr(settings, "notification_debug_fail_processing", False),
            )
            processor = ProcessPendingInboxUseCase(
                inbox_repo=inbox_repo,
                process_event_use_case=process_event_uc,
                clock=clock,
            )
            result = await processor.execute(
                ProcessPendingInboxRequest(limit=settings.notification_worker_batch_size)
            )
            print(f"Notification worker processed pending inbox: {result}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
