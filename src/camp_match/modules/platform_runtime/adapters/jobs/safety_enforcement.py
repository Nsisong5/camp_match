from __future__ import annotations

from typing import Any, cast

from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
)
from camp_match.modules.housing.application.use_cases.unit_listing_management import (
    LiftListingSuspensionUseCase,
    SuspendListingForSafetyUseCase,
)
from camp_match.modules.identity.adapters.persistence.repository import (
    SqlAlchemyIdentityRepository,
)
from camp_match.modules.identity.application.use_cases.disable_account import (
    DisableAccountUseCase,
)
from camp_match.modules.identity.application.use_cases.reactivate_account import (
    ReactivateAccountUseCase,
)
from camp_match.modules.messaging.adapters.persistence.repository import (
    SqlAlchemyRestrictionRepository,
)
from camp_match.modules.messaging.adapters.security.authorization import (
    InProcessAuthorizationService as MessagingAuthService,
)
from camp_match.modules.messaging.application.use_cases.restriction_management import (
    LiftCommunicationRestrictionUseCase,
    RestrictCommunicationUseCase,
)
from camp_match.modules.profile.adapters.persistence.repository import (
    SqlAlchemyProfileRepository,
)
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import (
    SqlAlchemyRoleRepository,
)
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.trust_safety.adapters.enforcement.account_enforcer import (
    InProcessAccountEnforcer,
)
from camp_match.modules.trust_safety.adapters.enforcement.communication_enforcer import (
    InProcessCommunicationEnforcer,
)
from camp_match.modules.trust_safety.adapters.enforcement.listing_enforcer import (
    InProcessListingEnforcer,
)
from camp_match.modules.trust_safety.adapters.persistence.case_repository import (
    SqlAlchemyCaseRepository,
)
from camp_match.modules.trust_safety.adapters.persistence.enforcement_repository import (
    SqlAlchemyEnforcementRepository,
)
from camp_match.modules.trust_safety.application.use_cases.process_enforcement_queue import (
    ProcessEnforcementQueueUseCase,
)
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


def build_safety_enforcement_job(
    session_factory: Any,
    session: Any = None,
    clock: Any = None,
    settings: Any = None,
    event_bus: Any = None,
) -> Any:
    if clock is None and settings is None and session is not None and hasattr(session, "now"):
        clock = session
        from camp_match.config.settings import get_settings
        settings = get_settings()
    elif clock is None and settings is not None and session is not None and hasattr(session, "now"):
        clock = session

    if clock is None:
        from camp_match.platform.clock import get_clock
        clock = get_clock()
    if settings is None:
        from camp_match.config.settings import get_settings
        settings = get_settings()

    async def run() -> None:
        async with session_factory() as db_session:
            enforcement_repo = SqlAlchemyEnforcementRepository(db_session)
            case_repo = SqlAlchemyCaseRepository(db_session)
            identity_repo = SqlAlchemyIdentityRepository(db_session)
            uow = SqlAlchemyUnitOfWork(db_session)
            account_enforcer = InProcessAccountEnforcer(
                DisableAccountUseCase(identity_repo, clock, event_bus, uow),
                ReactivateAccountUseCase(identity_repo, clock, event_bus, uow),
            )
            listing_repo = SqlAlchemyListingRepository(db_session)
            prop_repo = SqlAlchemyPropertyRepository(db_session)
            auth_service = MessagingAuthService(
                AuthorizeActionUseCase(
                    SqlAlchemyRoleRepository(db_session),
                    SecurityProfileProvider(
                        GetCurrentUserProfileUseCase(
                            SqlAlchemyProfileRepository(db_session)
                        )
                    ),
                )
            )
            suspend_uc = SuspendListingForSafetyUseCase(
                listing_repo, prop_repo, auth_service, uow, clock
            )
            lift_uc = LiftListingSuspensionUseCase(
                listing_repo, prop_repo, auth_service, uow, clock
            )
            listing_enforcer = InProcessListingEnforcer(suspend_uc, lift_uc)
            restriction_repo = SqlAlchemyRestrictionRepository(db_session)
            restrict_uc = RestrictCommunicationUseCase(
                restriction_repo, auth_service, uow
            )
            lift_comm_uc = LiftCommunicationRestrictionUseCase(
                restriction_repo, auth_service, uow
            )
            communication_enforcer = InProcessCommunicationEnforcer(
                restrict_uc, lift_comm_uc
            )
            processor = ProcessEnforcementQueueUseCase(
                enforcement_repo=cast(Any, enforcement_repo),
                case_repo=cast(Any, case_repo),
                account_enforcer=account_enforcer,
                listing_enforcer=listing_enforcer,
                communication_enforcer=communication_enforcer,
                event_bus=event_bus,
                uow=uow,
                clock=clock,
            )
            await processor.execute(
                limit=getattr(settings, "safety_worker_batch_size", 100)
            )

    return run
