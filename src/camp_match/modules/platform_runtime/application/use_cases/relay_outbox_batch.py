from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from camp_match.modules.platform_runtime.domain.outbox import calculate_backoff
from camp_match.shared_kernel.application.event_bus import publish_best_effort
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


@dataclass(frozen=True)
class RelayResult:
    claimed: int
    delivered: int
    failed: int
    dead: int


class RelayOutboxBatchUseCase:
    def __init__(
        self,
        session_factory: Any,
        outbox_repo_factory: Any,
        event_registry: Any,
        event_bus: Any,
        clock: Any,
        settings: Any,
    ) -> None:
        self._session_factory = session_factory
        self._outbox_repo_factory = outbox_repo_factory
        self._event_registry = event_registry
        self._event_bus = event_bus
        self._clock = clock
        self._settings = settings

    async def execute(
        self,
        batch_size: int,
        specific_event_ids: list[EntityId] | None = None,
    ) -> RelayResult:
        now = self._clock.now() if self._clock else datetime.now(UTC)
        claimed_count = 0
        delivered_count = 0
        failed_count = 0
        dead_count = 0

        async with self._session_factory() as session:
            outbox_repo = self._outbox_repo_factory(session)
            if specific_event_ids:
                rows = await outbox_repo.get_by_ids(specific_event_ids)
            else:
                rows = await outbox_repo.claim_due(batch_size, now)

            claimed_count = len(rows)
            if not rows:
                return RelayResult(0, 0, 0, 0)

            for row in rows:
                event_id = row.event_id
                attempts = row.attempts + 1
                error_msg = None
                domain_event = None

                try:
                    domain_event = self._event_registry.from_payload(
                        row.event_type,
                        row.payload,
                        event_id,
                        row.occurred_at,
                    )
                except Exception as exc:
                    error_msg = str(exc)

                if domain_event is not None:
                    try:
                        await publish_best_effort(
                            self._event_bus, domain_event, logger
                        )
                    except Exception as exc:
                        error_msg = str(exc)
                        domain_event = None

                if domain_event is not None:
                    await outbox_repo.mark_delivered(event_id, now)
                    delivered_count += 1
                else:
                    max_attempts = getattr(
                        self._settings, "platform_outbox_max_attempts", 8
                    )
                    base_sec = getattr(
                        self._settings, "platform_outbox_backoff_base_seconds", 5
                    )
                    cap_sec = getattr(
                        self._settings, "platform_outbox_backoff_cap_seconds", 300
                    )

                    if attempts >= max_attempts:
                        await outbox_repo.mark_dead(
                            event_id, error_msg or "Unknown error", now, attempts
                        )
                        dead_count += 1
                    else:
                        backoff = calculate_backoff(
                            attempts, base_sec, cap_sec
                        )
                        next_attempt = now + timedelta(seconds=backoff)
                        await outbox_repo.record_failure(
                            event_id, attempts, next_attempt, error_msg or "Unknown error"
                        )
                        failed_count += 1

            await session.commit()

        return RelayResult(
            claimed=claimed_count,
            delivered=delivered_count,
            failed=failed_count,
            dead=dead_count,
        )
