"""Platform event bus factory and accessor."""
from __future__ import annotations

import asyncio
import importlib
from typing import Any

from camp_match.platform.in_memory_event_bus import InMemoryEventBus


def build_event_bus(
    session_factory: Any, clock: Any, settings: Any
) -> InMemoryEventBus:
    bus = InMemoryEventBus()
    try:
        reg_mod = importlib.import_module(
            "camp_match.modules.notification.adapters.events.registration"
        )
        reg_mod.register_notification_subscribers(bus, session_factory, clock, settings)
    except ImportError:
        pass
    return bus


_event_bus_by_loop: dict[Any, InMemoryEventBus] = {}


def get_event_bus(
    session_factory: Any = None, clock: Any = None, settings: Any = None
) -> InMemoryEventBus:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop in _event_bus_by_loop:
        return _event_bus_by_loop[loop]

    from camp_match.config.settings import get_settings
    from camp_match.platform.clock import get_clock
    from camp_match.platform.db.session import create_engine, create_session_factory

    cfg = settings or get_settings()
    clk = clock or get_clock()
    if session_factory is not None:
        sf = session_factory
    else:
        engine = create_engine(cfg)
        sf = create_session_factory(engine)
    
    bus = build_event_bus(sf, clk, cfg)
    if loop is not None:
        _event_bus_by_loop[loop] = bus
    return bus
