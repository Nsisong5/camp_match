#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from contextlib import suppress

import structlog

from camp_match.config.settings import get_settings
from camp_match.modules.platform_runtime.adapters.jobs.registry import get_job_registry
from camp_match.modules.platform_runtime.adapters.persistence.job_repository import (
    SqlAlchemyJobRepository,
)
from camp_match.modules.platform_runtime.application.use_cases.get_job_statuses import (
    GetJobStatusesUseCase,
)
from camp_match.modules.platform_runtime.application.use_cases.run_job import (
    RunJobUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.event_bus import build_event_bus

logger = structlog.get_logger()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Camp Match Unified Platform Worker"
    )
    parser.add_argument(
        "--once", action="store_true", help="Run each enabled job once and exit"
    )
    parser.add_argument(
        "--only", type=str, help="Run only the specified job name"
    )
    parser.add_argument(
        "--list", action="store_true", help="List registered jobs"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Print health statuses of all jobs"
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    clock = get_clock()
    event_bus = build_event_bus(session_factory, clock, settings)

    registry = get_job_registry(settings)
    disabled_str = getattr(settings, "platform_jobs_disabled", "")
    disabled_jobs = {j.strip() for j in disabled_str.split(",") if j.strip()}

    if "payment_auto_release" not in disabled_jobs and "payment_release_warnings" in disabled_jobs:
        logger.warning(
            "automatic_release_enabled_without_warnings",
            message="automatic release will never fire: no warnings are being sent",
        )

    if args.list:
        print("Registered Platform Jobs:")
        for name, (interval, _) in registry.items():
            status = "DISABLED" if name in disabled_jobs else "ENABLED"
            print(f" - {name}: interval={interval}s, status={status}")
        await engine.dispose()
        return

    if args.stats:
        get_statuses = GetJobStatusesUseCase(
            session_factory, SqlAlchemyJobRepository, clock, settings
        )
        statuses = await get_statuses.execute()
        print("Platform Job Statuses & Health:")
        for s in statuses:
            print(
                f" - {s.name}: health={s.health}, "
                f"failures={s.consecutive_failures}, next_run={s.next_run_at}"
            )
        await engine.dispose()
        return

    run_job_uc = RunJobUseCase(
        session_factory, SqlAlchemyJobRepository, clock, settings
    )
    lease_holder = "worker_pid_" + str(asyncio.get_running_loop())

    shutdown_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("worker_shutdown_signal_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, handle_signal)

    jobs_to_run = list(registry.items())
    if args.only:
        if args.only not in registry:
            print(f"Error: Job '{args.only}' not found in registry.")
            await engine.dispose()
            sys.exit(1)
        jobs_to_run = [(args.only, registry[args.only])]

    async def run_worker_loop() -> None:
        while not shutdown_event.is_set():
            for name, (interval, builder_fn) in jobs_to_run:
                if shutdown_event.is_set():
                    break
                if name in disabled_jobs:
                    logger.info("job_skipped_disabled", job_name=name)
                    continue

                async with session_factory() as session:
                    job_fn = builder_fn(
                        session_factory, session, clock, settings, event_bus
                    )

                try:
                    res = await run_job_uc.execute(
                        name, interval, job_fn, lease_holder
                    )
                    logger.info(
                        "job_execution_result", job_name=name, result=res
                    )
                except Exception as exc:
                    logger.error(
                        "job_unexpected_error", job_name=name, error=str(exc)
                    )

            if args.once:
                break
            await asyncio.sleep(1)

    try:
        await run_worker_loop()
    finally:
        await engine.dispose()


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
