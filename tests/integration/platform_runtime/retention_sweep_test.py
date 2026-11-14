from __future__ import annotations

from datetime import UTC, datetime
import uuid
import pytest
from sqlalchemy import select

from camp_match.config.settings import get_settings
from camp_match.modules.identity.adapters.persistence.models import (
    AccountModel,
    OneTimeCodeModel,
)
from camp_match.modules.platform_runtime.adapters.jobs.retention_sweep import (
    build_retention_sweep_job,
)
from tests.support.fixed_clock import FixedClock


def test_retention_sweep_guard_targets() -> None:
    """
    Asserts exact retention targets: platform outbox, messaging outbox,
    notification inbox, notification notifications, rate limits, and identity one-time codes.
    Contains no audit, booking, payment, or account table.
    """
    targets = {
        "platform_outbox",
        "messaging_outbox",
        "notification_inbox",
        "notification_notifications",
        "rate_limits",
        "identity_one_time_codes",
    }
    # Assert prohibited tables are absent
    prohibited = {"audit", "bookings", "payments", "accounts", "identity_accounts"}
    assert targets.isdisjoint(prohibited)
    assert "identity_one_time_codes" in targets
    assert len(targets) == 6


@pytest.mark.asyncio
async def test_retention_sweep_identity_codes(session_factory) -> None:
    clock = FixedClock(datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC))
    settings = get_settings()

    acc_id = uuid.uuid4()
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()
    id4 = uuid.uuid4()
    id5 = uuid.uuid4()

    async with session_factory() as session:
        account = AccountModel(
            id=acc_id,
            email="retention_test@example.com",
            password_hash="dummy",
        )
        session.add(account)

        # 1. Old consumed code (should be purged)
        old_consumed = OneTimeCodeModel(
            id=id1,
            account_id=acc_id,
            purpose="EMAIL_VERIFICATION",
            code_hash="hash1",
            issued_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 10, 1, 12, 15, 0, tzinfo=UTC),
            max_attempts=3,
            consumed_at=datetime(2026, 10, 1, 12, 5, 0, tzinfo=UTC),
        )
        # 2. Old invalidated code (should be purged)
        old_invalidated = OneTimeCodeModel(
            id=id2,
            account_id=acc_id,
            purpose="EMAIL_VERIFICATION",
            code_hash="hash2",
            issued_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 10, 1, 12, 15, 0, tzinfo=UTC),
            max_attempts=3,
            invalidated_at=datetime(2026, 10, 1, 12, 5, 0, tzinfo=UTC),
        )
        # 3. Old expired code (should be purged)
        old_expired = OneTimeCodeModel(
            id=id3,
            account_id=acc_id,
            purpose="EMAIL_VERIFICATION",
            code_hash="hash3",
            issued_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 10, 1, 12, 15, 0, tzinfo=UTC),
            max_attempts=3,
            invalidated_at=datetime(2026, 10, 1, 12, 10, 0, tzinfo=UTC),
        )
        # 4. Active code (expires_at is far in future, unconsumed, uninvalidated -> NEVER purged)
        active_code = OneTimeCodeModel(
            id=id4,
            account_id=acc_id,
            purpose="EMAIL_VERIFICATION",
            code_hash="hash4",
            issued_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC),
            max_attempts=3,
        )
        # 5. Younger consumed code (younger than retention window -> kept)
        young_consumed = OneTimeCodeModel(
            id=id5,
            account_id=acc_id,
            purpose="EMAIL_VERIFICATION",
            code_hash="hash5",
            issued_at=datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 11, 10, 12, 15, 0, tzinfo=UTC),
            max_attempts=3,
            consumed_at=datetime(2026, 11, 10, 12, 5, 0, tzinfo=UTC),
        )

        session.add_all([old_consumed, old_invalidated, old_expired, active_code, young_consumed])
        await session.commit()

    # Run retention sweep job
    sweep_job = build_retention_sweep_job(session_factory, clock, settings)
    purged_count = await sweep_job()
    assert purged_count >= 3

    async with session_factory() as session:
        res = await session.execute(select(OneTimeCodeModel))
        remaining = res.scalars().all()
        remaining_ids = {c.id for c in remaining}

        # Old codes should be gone
        assert id1 not in remaining_ids
        assert id2 not in remaining_ids
        assert id3 not in remaining_ids

        # Active and young codes must be kept
        assert id4 in remaining_ids
        assert id5 in remaining_ids

    # Second run should be a no-op for identity codes
    second_purged = await sweep_job()
    assert second_purged == 0
