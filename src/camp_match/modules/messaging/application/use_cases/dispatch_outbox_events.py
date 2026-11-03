from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from camp_match.modules.messaging.application.ports.outbound import MessageEventDispatcher

logger = structlog.get_logger()


class DispatchOutboxEventsResult:
    def __init__(self, claimed: int, dispatched: int, failed: int) -> None:
        self.claimed = claimed
        self.dispatched = dispatched
        self.failed = failed


class DispatchOutboxEvents:
    def __init__(
        self,
        session_factory: Any,
        dispatcher: MessageEventDispatcher,
        clock: Any,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._clock = clock

    async def execute(self, limit: int) -> DispatchOutboxEventsResult:
        from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
            SqlAlchemyOutboxRepository,
        )
        from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork

        def get_session():
            if hasattr(self._session_factory, "__aenter__"):
                class DirectCtx:
                    async def __aenter__(self):
                        return self._session
                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        pass
                    def __init__(self, s):
                        self._session = s
                return DirectCtx(self._session_factory)
            else:
                return self._session_factory()

        async with get_session() as session:
            outbox_repo = SqlAlchemyOutboxRepository(session)
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                pending = await outbox_repo.claim_pending(limit)

        claimed = len(pending)
        dispatched = 0
        failed = 0

        for event in pending:
            try:
                await self._dispatcher.dispatch(event.event_id)
                async with get_session() as session:
                    outbox_repo = SqlAlchemyOutboxRepository(session)
                    uow = SqlAlchemyUnitOfWork(session)
                    async with uow:
                        await outbox_repo.mark_dispatched(event.event_id, self._clock.now())
                dispatched += 1
            except Exception as e:
                logger.error("outbox_dispatch_failed", event_id=str(event.event_id), error=str(e))
                try:
                    async with get_session() as session:
                        outbox_repo = SqlAlchemyOutboxRepository(session)
                        uow = SqlAlchemyUnitOfWork(session)
                        async with uow:
                            await outbox_repo.record_failure(event.event_id, type(e).__name__)
                except Exception:
                    pass
                failed += 1

        return DispatchOutboxEventsResult(claimed=claimed, dispatched=dispatched, failed=failed)
