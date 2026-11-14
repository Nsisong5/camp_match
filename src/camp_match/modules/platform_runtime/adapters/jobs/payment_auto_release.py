from __future__ import annotations

from typing import Any


def build_payment_auto_release_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    async def run() -> None:
        # Payment automatic release job (disabled by default)
        pass

    return run
