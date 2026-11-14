from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.shared_kernel.domain.events import DomainEvent
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()

_global_event_registry: Any = None
_global_outbox_nudge: Any = None
_global_clock: Any = None


def configure_unit_of_work_outbox(
    event_registry: Any, outbox_nudge: Any, clock: Any
) -> None:
    global _global_event_registry, _global_outbox_nudge, _global_clock
    _global_event_registry = event_registry
    _global_outbox_nudge = outbox_nudge
    _global_clock = clock


def _make_json_serializable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, EntityId):
        return str(obj.value)
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    return obj


class UnitOfWork(Protocol):
    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    def add_event(self, event: DomainEvent) -> None: ...


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        session: AsyncSession,
        event_registry: Any | None = None,
        outbox_nudge: Any | None = None,
        clock: Any | None = None,
    ) -> None:
        self._session = session
        self._event_registry = event_registry or _global_event_registry
        self._outbox_nudge = outbox_nudge or _global_outbox_nudge
        self._clock = clock or _global_clock
        self._pending_events: list[DomainEvent] = []

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is not None:
            await self.rollback()

    def add_event(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    async def commit(self) -> None:
        event_ids_to_nudge: list[EntityId] = []
        if self._pending_events:
            now = self._clock.now() if self._clock else datetime.now(UTC)
            outbox_repo = SqlAlchemyOutboxRepository(self._session)
            for event in self._pending_events:
                event_id = event.event_id
                occurred_at = event.occurred_at or now
                event_type = type(event).__name__
                payload: dict[str, Any] = {}

                if self._event_registry:
                    try:
                        event_type, payload = self._event_registry.to_payload(event)
                    except Exception:
                        payload = {
                            k: str(v) if isinstance(v, EntityId) else v
                            for k, v in event.__dict__.items()
                        }
                else:
                    payload = {
                        k: str(v) if isinstance(v, EntityId) else v
                        for k, v in event.__dict__.items()
                    }

                payload = _make_json_serializable(payload)

                await outbox_repo.add(
                    event_id=event_id,
                    event_type=event_type,
                    payload=payload,
                    occurred_at=occurred_at,
                    created_at=now,
                    next_attempt_at=now,
                )
                event_ids_to_nudge.append(event_id)

        await self._session.commit()
        committed_events = list(event_ids_to_nudge)
        self._pending_events.clear()

        if committed_events and self._outbox_nudge:
            try:
                await self._outbox_nudge.nudge(committed_events)
            except Exception as exc:
                logger.warning("outbox_nudge_failed_after_commit", error=str(exc))

    async def rollback(self) -> None:
        self._pending_events.clear()
        await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        return self._session


async def get_unit_of_work(session: AsyncSession = ...) -> SqlAlchemyUnitOfWork:  # type: ignore
    return SqlAlchemyUnitOfWork(session)
