from __future__ import annotations

from typing import Any


def build_payment_recovery_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    async def run() -> None:
        # Payment recovery late-signal / uncertain attempt handler placeholder
        pass

    return run
