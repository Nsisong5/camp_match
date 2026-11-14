"""Identity events subscriber for housing module."""
from __future__ import annotations

import structlog
from typing import Any

from camp_match.modules.identity.application.ports.events import (
    AccountDisabled,
    AccountReactivated,
)
from camp_match.modules.housing.application.use_cases.disabled_owner_suspension import (
    SuspendListingsForDisabledOwnerUseCase,
    LiftOwnerAccountSuspensionsUseCase,
)

logger = structlog.get_logger(__name__)


def register_identity_subscribers(
    bus: Any,
    session_factory: Any,
    clock: Any,
    settings: Any,
) -> None:
    async def handle_account_disabled(event: AccountDisabled) -> None:
        try:
            uc = SuspendListingsForDisabledOwnerUseCase(session_factory, settings)
            await uc(event.user_id, event.event_id)
        except Exception as e:
            logger.error(
                "identity_subscriber_account_disabled_failed",
                error=str(e),
                event_id=event.event_id,
            )
            raise

    async def handle_account_reactivated(event: AccountReactivated) -> None:
        try:
            uc = LiftOwnerAccountSuspensionsUseCase(session_factory, settings)
            await uc(event.user_id, event.event_id)
        except Exception as e:
            logger.error(
                "identity_subscriber_account_reactivated_failed",
                error=str(e),
                event_id=event.event_id,
            )
            raise

    bus.subscribe(AccountDisabled, handle_account_disabled)
    bus.subscribe(AccountReactivated, handle_account_reactivated)
