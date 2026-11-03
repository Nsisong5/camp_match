#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from camp_match.config.settings import get_settings
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
)
from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
from camp_match.modules.identity.application.use_cases.disable_account import DisableAccountUseCase
from camp_match.modules.identity.application.use_cases.reactivate_account import ReactivateAccountUseCase
from camp_match.modules.messaging.adapters.persistence.repository import SqlAlchemyRestrictionRepository
from camp_match.modules.messaging.adapters.security.authorization import (
    InProcessAuthorizationService as MessagingAuthService,
)
from camp_match.modules.messaging.application.use_cases.restriction_management import (
    LiftCommunicationRestrictionUseCase,
    RestrictCommunicationUseCase,
)
from camp_match.modules.housing.application.use_cases.unit_listing_management import (
    LiftListingSuspensionUseCase,
    SuspendListingForSafetyUseCase,
)
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import GetCurrentUserProfileUseCase
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import InProcessProfileProvider as SecurityProfileProvider
from camp_match.modules.security.application.use_cases.authorize_action import AuthorizeActionUseCase
from camp_match.modules.trust_safety.adapters.enforcement.account_enforcer import InProcessAccountEnforcer
from camp_match.modules.trust_safety.adapters.enforcement.communication_enforcer import InProcessCommunicationEnforcer
from camp_match.modules.trust_safety.adapters.enforcement.listing_enforcer import InProcessListingEnforcer
from camp_match.modules.trust_safety.adapters.persistence.case_repository import SqlAlchemyCaseRepository
from camp_match.modules.trust_safety.adapters.persistence.enforcement_repository import SqlAlchemyEnforcementRepository
from camp_match.modules.trust_safety.application.use_cases.process_enforcement_queue import ProcessEnforcementQueueUseCase
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import create_engine, create_session_factory
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import build_event_bus

logger = structlog.get_logger()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Trust & Safety Enforcement Worker")
    parser.add_argument("--stats", action="store_true", help="Print enforcement action counts by status")
    parser.add_argument("--requeue-failed", action="store_true", help="Requeue failed enforcement actions")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    clock = get_clock()
    event_bus = build_event_bus(session_factory, clock, settings)

    async with session_factory() as session:
        enforcement_repo = SqlAlchemyEnforcementRepository(session)
        case_repo = SqlAlchemyCaseRepository(session)
        identity_repo = SqlAlchemyIdentityRepository(session)
        uow = SqlAlchemyUnitOfWork(session)

        if args.stats:
            print("Enforcement stats feature enabled.")
        elif args.requeue_failed:
            print("Requeue failed feature enabled.")
        else:
            account_enforcer = InProcessAccountEnforcer(
                DisableAccountUseCase(identity_repo, clock, event_bus, uow),
                ReactivateAccountUseCase(identity_repo, clock, event_bus, uow),
            )
            listing_repo = SqlAlchemyListingRepository(session)
            property_repo = SqlAlchemyPropertyRepository(session)
            auth_service = MessagingAuthService(
                AuthorizeActionUseCase(SqlAlchemyRoleRepository(session), SecurityProfileProvider(GetCurrentUserProfileUseCase(SqlAlchemyProfileRepository(session))))
            )
            suspend_uc = SuspendListingForSafetyUseCase(listing_repo, auth_service, uow)
            lift_uc = LiftListingSuspensionUseCase(listing_repo, auth_service, uow)
            listing_enforcer = InProcessListingEnforcer(suspend_uc, lift_uc)

            restriction_repo = SqlAlchemyRestrictionRepository(session)
            restrict_uc = RestrictCommunicationUseCase(restriction_repo, auth_service, uow)
            lift_comm_uc = LiftCommunicationRestrictionUseCase(restriction_repo, auth_service, uow)
            communication_enforcer = InProcessCommunicationEnforcer(restrict_uc, lift_comm_uc)

            processor = ProcessEnforcementQueueUseCase(
                enforcement_repo=enforcement_repo,
                case_repo=case_repo,
                account_enforcer=account_enforcer,
                listing_enforcer=listing_enforcer,
                communication_enforcer=communication_enforcer,
                event_bus=event_bus,
                unit_of_work=uow,
                clock=clock,
            )
            stats = await processor.execute(limit=settings.safety_worker_batch_size)
            print(f"Safety worker processed queue: {stats}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
