from __future__ import annotations

from datetime import UTC, datetime
import pytest
from sqlalchemy import select

from camp_match.config.settings import get_settings
from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
from camp_match.modules.identity.adapters.persistence.models import AccountModel
from camp_match.modules.identity.application.use_cases.disable_account import DisableAccountUseCase
from camp_match.modules.identity.application.ports.inbound import UpdateStatusRequest
from camp_match.modules.platform_runtime.adapters.persistence.models import PlatformOutboxModel
from camp_match.modules.platform_runtime.adapters.registry.setup import create_default_event_registry
from camp_match.modules.platform_runtime.adapters.nudge.outbox_nudge_listener import OutboxNudgeListener
from camp_match.modules.platform_runtime.application.use_cases.relay_outbox_batch import RelayOutboxBatchUseCase
from camp_match.modules.platform_runtime.adapters.persistence.outbox_repository import SqlAlchemyOutboxRepository
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork, configure_unit_of_work_outbox
from camp_match.platform.in_memory_event_bus import InMemoryEventBus
from camp_match.shared_kernel.domain.identifiers import EntityId
from tests.support.fixed_clock import FixedClock


@pytest.mark.asyncio
async def test_disable_account_writes_outbox(session_factory) -> None:
    settings = get_settings()
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC))
    event_bus = InMemoryEventBus()

    registry = create_default_event_registry()
    relay_uc = RelayOutboxBatchUseCase(session_factory, SqlAlchemyOutboxRepository, registry, event_bus, clock, settings)
    nudge_listener = OutboxNudgeListener(relay_uc, settings)
    configure_unit_of_work_outbox(registry, nudge_listener, clock)

    acc_id = EntityId.new()
    async with session_factory() as session:
        session.add(
            AccountModel(
                id=acc_id.value,
                email="test@example.com",
                password_hash="hash",
                status="ACTIVE",
                created_at=clock.now(),
                updated_at=clock.now(),
            )
        )
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyIdentityRepository(session)
        uow = SqlAlchemyUnitOfWork(session)
        use_case = DisableAccountUseCase(
            repository=repo,
            clock=clock,
            event_bus=event_bus,
            unit_of_work=uow,
        )
        await use_case.execute(UpdateStatusRequest(identity_id=str(acc_id)))

    # Verify outbox has identity.account_disabled event
    async with session_factory() as session:
        row = (await session.execute(
            select(PlatformOutboxModel).where(PlatformOutboxModel.event_type == "identity.account_disabled")
        )).scalar_one_or_none()
        assert row is not None
        assert row.status in ("PENDING", "DELIVERED")
        assert row.payload["user_id"] == str(acc_id)
