from __future__ import annotations

from typing import Any

from camp_match.modules.payment.adapters.persistence.repository import (
    SqlAlchemyDisputeRepository,
    SqlAlchemyReleaseScheduleRepository,
    SqlAlchemyTransactionReviewRepository,
)
from camp_match.modules.payment.adapters.security.release_approver_provider import ReleaseApproverProvider
from camp_match.modules.payment.application.use_cases.dispatch_release_warnings import (
    DispatchReleaseWarningsUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.payment.adapters.security.authorization import InProcessAuthorizationService
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork


def build_payment_release_warnings_job(
    session_factory: Any,
    session: Any,
    clock: Any,
    settings: Any,
    event_bus: Any,
) -> Any:
    async def run() -> None:
        async with session_factory() as db_session:
            schedule_repo = SqlAlchemyReleaseScheduleRepository(db_session)
            review_repo = SqlAlchemyTransactionReviewRepository(db_session)
            dispute_repo = SqlAlchemyDisputeRepository(db_session)
            role_repo = SqlAlchemyRoleRepository(db_session)
            profile_repo = SqlAlchemyProfileRepository(db_session)
            profile_uc = GetCurrentUserProfileUseCase(profile_repo)
            sec_profile_provider = SecurityProfileProvider(profile_uc)
            authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
            auth_service = InProcessAuthorizationService(authorize_uc)
            identity_repo = SqlAlchemyIdentityRepository(db_session)

            class IdentityQueryAdapter:
                async def get_identity_status(self, identity_id: Any) -> str | None:
                    acc = await identity_repo.get_by_id(identity_id)
                    return acc.status.value if acc and acc.status else None

            from camp_match.modules.security.application.use_cases.list_identities_holding_permission import (
                ListIdentitiesHoldingPermissionUseCase,
            )
            list_identities_uc = ListIdentitiesHoldingPermissionUseCase(role_repo)
            approver_provider = ReleaseApproverProvider(list_identities_uc, IdentityQueryAdapter())
            uow = SqlAlchemyUnitOfWork(db_session)

            uc = DispatchReleaseWarningsUseCase(
                schedule_repo=schedule_repo,
                review_repo=review_repo,
                dispute_repo=dispute_repo,
                approver_provider=approver_provider,
                uow=uow,
                clock=clock,
                settings_view=settings,
            )
            await uc.execute()

    return run
