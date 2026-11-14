from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from camp_match.shared_kernel.domain.identifiers import EntityId


@dataclass(frozen=True)
class OutboxRecord:
    event_id: EntityId
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
    attempts: int


class OutboxRepository(Protocol):
    async def add(
        self,
        event_id: EntityId,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        created_at: datetime,
        next_attempt_at: datetime,
    ) -> None: ...

    async def claim_due(self, limit: int, now: datetime) -> list[OutboxRecord]: ...

    async def get_by_ids(self, event_ids: list[EntityId]) -> list[OutboxRecord]: ...

    async def mark_delivered(self, event_id: EntityId, delivered_at: datetime) -> None: ...

    async def record_failure(
        self,
        event_id: EntityId,
        attempts: int,
        next_attempt_at: datetime,
        last_error: str,
    ) -> None: ...

    async def mark_dead(
        self,
        event_id: EntityId,
        last_error: str,
        now: datetime,
        attempts: int,
    ) -> None: ...


@dataclass(frozen=True)
class JobStatusRecord:
    name: str
    enabled: bool
    interval_seconds: int
    last_started_at: datetime | None
    last_finished_at: datetime | None
    next_run_at: datetime
    lease_holder: str | None
    lease_expires_at: datetime | None
    consecutive_failures: int
    last_error: str | None
    health: str


class JobRepository(Protocol):
    async def ensure_job(self, name: str, interval_seconds: int, now: datetime) -> None: ...

    async def try_acquire(
        self,
        name: str,
        lease_holder: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> bool: ...

    async def record_success(
        self,
        name: str,
        started_at: datetime,
        finished_at: datetime,
        next_run_at: datetime,
    ) -> None: ...

    async def record_failure(
        self,
        name: str,
        started_at: datetime,
        error: str,
        next_run_at: datetime,
    ) -> None: ...

    async def list_statuses(
        self,
        disabled_jobs: set[str],
        stale_multiplier: int,
        failing_threshold: int,
        now: datetime,
    ) -> list[JobStatusRecord]: ...
