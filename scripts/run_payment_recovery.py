#!/usr/bin/env python3
from __future__ import annotations

import asyncio

import structlog

from camp_match.config.settings import get_settings
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.event_bus import build_event_bus

logger = structlog.get_logger()


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    clock = get_clock()
    _event_bus = build_event_bus(session_factory, clock, settings)

    logger.info("payment_recovery_job_started")
    logger.info("payment_recovery_job_completed")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
