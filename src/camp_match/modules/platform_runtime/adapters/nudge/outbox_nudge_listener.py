from __future__ import annotations

from contextlib import suppress
from typing import Any

from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import (
    RelayOutboxBatchUseCase,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class OutboxNudgeListener:
    def __init__(self, relay_use_case: RelayOutboxBatchUseCase, settings: Any) -> None:
        self._relay_use_case = relay_use_case
        self._settings = settings

    async def nudge(self, event_ids: list[EntityId]) -> None:
        if not event_ids:
            return
        if not getattr(self._settings, "platform_outbox_nudge_enabled", True):
            return
        debug_disable = getattr(
            self._settings, "platform_debug_disable_nudge", False
        )
        app_env = getattr(self._settings, "app_env", "local")
        if debug_disable and app_env in ("local", "test"):
            return

        with suppress(Exception):
            await self._relay_use_case.execute(
                batch_size=len(event_ids), specific_event_ids=event_ids
            )
