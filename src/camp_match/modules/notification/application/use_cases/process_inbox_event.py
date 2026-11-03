"""Process inbox event use case."""
from __future__ import annotations

from datetime import timedelta

import structlog

from camp_match.modules.notification.application.policies.recipient_policies import (
    resolve_recipients,
)
from camp_match.modules.notification.application.ports.inbound import (
    CreateOutcome,
    ProcessInboxEventRequest,
    ProcessOutcome,
)
from camp_match.modules.notification.application.ports.outbound import (
    InboxRepository,
    NotificationRepository,
    PropertyOwnerProvider,
)
from camp_match.modules.notification.domain.entities import Notification
from camp_match.modules.notification.domain.inbox import next_delay_seconds
from camp_match.modules.notification.domain.templates import render
from camp_match.modules.notification.domain.value_objects import NotificationType
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock
from camp_match.shared_kernel.domain.identifiers import EntityId

logger = structlog.get_logger()


class ProcessInboxEventUseCase:
    def __init__(
        self,
        inbox_repo: InboxRepository,
        notification_repo: NotificationRepository,
        property_owner_provider: PropertyOwnerProvider,
        uow: UnitOfWork,
        clock: Clock,
        max_attempts: int = 8,
        backoff_base: int = 30,
        backoff_cap: int = 3600,
        debug_fail: bool = False,
    ) -> None:
        self.inbox_repo = inbox_repo
        self.notification_repo = notification_repo
        self.property_owner_provider = property_owner_provider
        self.uow = uow
        self.clock = clock
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.debug_fail = debug_fail

    async def execute(self, request: ProcessInboxEventRequest) -> ProcessOutcome:
        now = self.clock.now()
        row = None

        # Step 1: Claim and process within a single transaction UoW
        try:
            async with self.uow:
                row = await self.inbox_repo.claim(request.event_id)
                if not row:
                    await self.uow.commit()
                    return ProcessOutcome.SKIPPED

                if self.debug_fail:
                    raise RuntimeError("Debug forced processing failure")

                # Step 2: Parse and resolve recipients
                try:
                    supported_types = {t.value for t in NotificationType}
                    if row.event_type not in supported_types:
                        raise ValueError(f"Unsupported event type: {row.event_type}")

                    async def get_owner_fn(prop_id: EntityId) -> EntityId | None:
                        return await self.property_owner_provider.get_owner(prop_id)

                    drafts = await resolve_recipients(
                        row.event_type, row.payload, get_owner_fn
                    )
                except Exception as parse_err:
                    await self.uow.rollback()
                    async with self.uow:
                        await self.inbox_repo.mark_rejected(
                            request.event_id, "invalid_payload", now
                        )
                        await self.uow.commit()
                    logger.warning(
                        "notification_event_rejected",
                        event_id=request.event_id,
                        error=str(parse_err),
                    )
                    return ProcessOutcome.REJECTED

                # Step 3 & 4: Create notifications and mark processed
                for draft in drafts:
                    title, body = render(draft.type)
                    notification = Notification(
                        id=EntityId.new(),
                        recipient_id=draft.recipient_id,
                        type=draft.type,
                        category=draft.type.category,
                        title=title,
                        body=body,
                        target=draft.target,
                        group_key=draft.group_key,
                        source_event_id=request.event_id,
                        created_at=now,
                        latest_event_at=now,
                    )
                    outcome = await self.notification_repo.create_or_collapse(
                        notification
                    )
                    if outcome == CreateOutcome.CREATED:
                        logger.info(
                            "notification_created",
                            notification_id=notification.id.value,
                        )
                    else:
                        logger.info(
                            "notification_collapsed", group_key=draft.group_key
                        )

                await self.inbox_repo.mark_processed(request.event_id, now)
                await self.uow.commit()
                return ProcessOutcome.PROCESSED

        except Exception as proc_err:
            if isinstance(proc_err, RuntimeError) and str(proc_err) == "Debug forced processing failure":
                # Fall through to failure handling
                pass
            elif not row:
                raise

            attempts = row.attempts + 1 if row else 1
            dead = attempts >= self.max_attempts
            delay = next_delay_seconds(
                attempts, self.backoff_base, self.backoff_cap
            )
            next_attempt = now + timedelta(seconds=delay)

            async with self.uow:
                await self.inbox_repo.record_failure(
                    request.event_id,
                    type(proc_err).__name__,
                    next_attempt,
                    dead,
                )
                await self.uow.commit()

            if dead:
                logger.error(
                    "notification_event_dead",
                    event_id=request.event_id,
                    attempts=attempts,
                )
            else:
                logger.warning(
                    "notification_processing_failed",
                    event_id=request.event_id,
                    event_type=row.event_type if row else "unknown",
                    attempt=attempts,
                    error_class=type(proc_err).__name__,
                )
            return ProcessOutcome.FAILED
