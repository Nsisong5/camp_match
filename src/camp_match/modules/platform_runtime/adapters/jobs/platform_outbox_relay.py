from __future__ import annotations

from typing import Any

from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.modules.platform_runtime.adapters.registry.setup import (
    create_default_event_registry,
)
from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import (
    RelayOutboxBatchUseCase,
)


def build_platform_outbox_relay_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    registry = create_default_event_registry()
    use_case = RelayOutboxBatchUseCase(
        session_factory,
        SqlAlchemyOutboxRepository,
        registry,
        event_bus,
        clock,
        settings,
    )

    async def run() -> None:
        await use_case.execute(settings.platform_outbox_batch_size)

    return run
