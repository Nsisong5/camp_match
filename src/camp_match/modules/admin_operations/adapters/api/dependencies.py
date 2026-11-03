from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.config.settings import get_settings
from camp_match.modules.admin_operations.adapters.identity.account_provider import (
    InProcessAccountProvider,
)
from camp_match.modules.admin_operations.adapters.overview.messaging_source import (
    MessagingSourceAdapter,
)
from camp_match.modules.admin_operations.adapters.overview.notification_source import (
    NotificationSourceAdapter,
)
from camp_match.modules.admin_operations.adapters.overview.payment_source import (
    PaymentSourceAdapter,
)
from camp_match.modules.admin_operations.adapters.overview.safety_source import (
    SafetySourceAdapter,
)
from camp_match.modules.admin_operations.adapters.overview.verification_source import (
    VerificationSourceAdapter,
)
from camp_match.modules.admin_operations.adapters.persistence.audit_repository import (
    SqlAlchemyAuditRepository,
)
from camp_match.modules.admin_operations.adapters.persistence.issue_repository import (
    SqlAlchemyIssueRepository,
)
from camp_match.modules.admin_operations.adapters.recovery.notification_recovery import (
    InProcessNotificationRecovery,
)
from camp_match.modules.admin_operations.adapters.recovery.safety_recovery import (
    InProcessSafetyRecovery,
)
from camp_match.modules.admin_operations.adapters.security.authorizer import (
    InProcessAuthorizer,
)
from camp_match.modules.admin_operations.adapters.security.staff_role_provider import (
    InProcessStaffRoleProvider,
)
from camp_match.modules.admin_operations.application.services.audit_recorder import (
    AuditRecorder,
)
from camp_match.modules.admin_operations.application.use_cases.assign_issue import (
    AssignIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.change_issue_status import (
    ChangeIssueStatusUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.create_issue import (
    CreateIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.disable_account import (
    DisableAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_account import (
    GetAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_issue import (
    GetIssueUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.get_overview import (
    GetOverviewUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.grant_staff_role import (
    GrantStaffRoleUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_audit_events import (
    ListAuditEventsUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_issues import (
    ListIssuesUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.list_staff import (
    ListStaffUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.reactivate_account import (
    ReactivateAccountUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.requeue_dead_notification_events import (
    RequeueDeadNotificationEventsUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.requeue_failed_safety_enforcement import (
    RequeueFailedSafetyEnforcementUseCase,
)
from camp_match.modules.admin_operations.application.use_cases.revoke_staff_role import (
    RevokeStaffRoleUseCase as AdminRevokeStaffRoleUseCase,
)
from camp_match.modules.identity.adapters.persistence.repository import (
    SqlAlchemyIdentityRepository,
)
from camp_match.modules.identity.application.use_cases.disable_account import (
    DisableAccountUseCase as IdentityDisableAccount,
)
from camp_match.modules.identity.application.use_cases.get_identity import (
    GetIdentityByIdUseCase,
)
from camp_match.modules.identity.application.use_cases.reactivate_account import (
    ReactivateAccountUseCase as IdentityReactivateAccount,
)
from camp_match.modules.messaging.adapters.persistence.outbox_repository import (
    SqlAlchemyOutboxRepository,
)
from camp_match.modules.messaging.application.use_cases.get_outbox_stats import (
    GetOutboxStatsUseCase,
)
from camp_match.modules.notification.adapters.persistence.inbox_repository import (
    SqlAlchemyInboxRepository as SqlAlchemyNotificationInboxRepository,
)
from camp_match.modules.notification.application.use_cases.get_inbox_stats import (
    GetInboxStatsUseCase,
)
from camp_match.modules.notification.application.use_cases.requeue_dead_events import (
    RequeueDeadEventsUseCase,
)
from camp_match.modules.payment.adapters.persistence.repository import (
    SqlAlchemyDisputeRepository,
)
from camp_match.modules.profile.adapters.persistence.repository import (
    SqlAlchemyProfileRepository,
)
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.adapters.persistence.repository import (
    SqlAlchemyRoleRepository,
)
from camp_match.modules.security.application.use_cases.assign_staff_role import (
    AssignStaffRoleUseCase,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.security.application.use_cases.get_assigned_roles import (
    GetAssignedRolesUseCase,
)
from camp_match.modules.security.application.use_cases.list_staff import (
    ListStaffUseCase as SecurityListStaffUseCase,
)
from camp_match.modules.security.application.use_cases.revoke_staff_role import (
    RevokeStaffRoleUseCase as SecurityRevokeStaffRoleUseCase,
)
from camp_match.modules.trust_safety.adapters.persistence.case_repository import (
    SqlAlchemyCaseRepository,
)
from camp_match.modules.trust_safety.adapters.persistence.enforcement_repository import (
    SqlAlchemyEnforcementRepository,
)
from camp_match.modules.trust_safety.adapters.persistence.report_repository import (
    SqlAlchemyReportRepository,
)
from camp_match.modules.trust_safety.application.use_cases.get_safety_overview import (
    GetSafetyOverviewUseCase,
)
from camp_match.modules.trust_safety.application.use_cases.process_enforcement_queue import (
    ProcessEnforcementQueueUseCase,
)
from camp_match.modules.verification.adapters.persistence.repository import (
    SQLAlchemyVerificationCaseRepository as SqlAlchemyVerificationCaseRepository,
)
from camp_match.modules.verification.application.use_cases.list_pending_reviews import (
    ListPendingReviewsUseCase,
)
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus


def get_issue_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyIssueRepository:
    return SqlAlchemyIssueRepository(session)


def get_audit_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyAuditRepository:
    return SqlAlchemyAuditRepository(session)


from camp_match.modules.security.application.ports.inbound import (
    AuthorizationRequest,
)


class SecurityAuthorizationServiceAdapter:
    def __init__(self, auth_uc: AuthorizeActionUseCase) -> None:
        self._auth_uc = auth_uc

    async def authorize(self, request: AuthorizationRequest) -> Any:
        return await self._auth_uc.execute(request)


def get_authorizer(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessAuthorizer:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    auth_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizer(auth_uc)


def get_staff_role_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessStaffRoleProvider:
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    auth_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    auth_service = SecurityAuthorizationServiceAdapter(auth_uc)
    assign_uc = AssignStaffRoleUseCase(role_repo, auth_service, session)
    revoke_uc = SecurityRevokeStaffRoleUseCase(role_repo, auth_service, session)
    list_uc = SecurityListStaffUseCase(role_repo, auth_service)
    get_roles_uc = GetAssignedRolesUseCase(role_repo)
    return InProcessStaffRoleProvider(assign_uc, revoke_uc, list_uc, get_roles_uc)


def get_account_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Any, Depends(get_clock)],
    event_bus: Annotated[Any, Depends(get_event_bus)],
) -> InProcessAccountProvider:
    identity_repo = SqlAlchemyIdentityRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    get_uc = GetIdentityByIdUseCase(identity_repo)
    disable_uc = IdentityDisableAccount(identity_repo, clock, event_bus, uow)
    reactivate_uc = IdentityReactivateAccount(identity_repo, clock, event_bus, uow)
    return InProcessAccountProvider(get_uc, disable_uc, reactivate_uc)


def get_audit_recorder(
    audit_repo: Annotated[SqlAlchemyAuditRepository, Depends(get_audit_repo)],
    request: Request,
    clock: Annotated[Any, Depends(get_clock)],
) -> AuditRecorder:
    return AuditRecorder(audit_repo, request.app.state.db_session_factory, clock)


def get_verification_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VerificationSourceAdapter:
    case_repo = SqlAlchemyVerificationCaseRepository(session)
    uc = ListPendingReviewsUseCase(case_repo, is_reviewer=True)
    return VerificationSourceAdapter(uc)


def get_payment_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> PaymentSourceAdapter:
    dispute_repo = SqlAlchemyDisputeRepository(session)
    return PaymentSourceAdapter(dispute_repo, authorizer)


def get_safety_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SafetySourceAdapter:
    report_repo = SqlAlchemyReportRepository(session)
    case_repo = SqlAlchemyCaseRepository(session)
    enforcement_repo = SqlAlchemyEnforcementRepository(session)
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    auth_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    uc = GetSafetyOverviewUseCase(report_repo, case_repo, enforcement_repo, auth_uc)
    return SafetySourceAdapter(uc)


def get_notification_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationSourceAdapter:
    inbox_repo = SqlAlchemyNotificationInboxRepository(session)
    uc = GetInboxStatsUseCase(inbox_repo)
    return NotificationSourceAdapter(uc)


def get_messaging_source(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Any, Depends(get_clock)],
) -> MessagingSourceAdapter:
    outbox_repo = SqlAlchemyOutboxRepository(session)
    uc = GetOutboxStatsUseCase(outbox_repo, clock)
    return MessagingSourceAdapter(uc)


def get_notification_recovery(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessNotificationRecovery:
    inbox_repo = SqlAlchemyNotificationInboxRepository(session)
    uow = SqlAlchemyUnitOfWork(session)
    uc = RequeueDeadEventsUseCase(inbox_repo, uow)
    return InProcessNotificationRecovery(uc)


def get_safety_recovery(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessSafetyRecovery:
    enforcement_repo = SqlAlchemyEnforcementRepository(session)
    case_repo = SqlAlchemyCaseRepository(session)
    decision_repo = None
    note_repo = None
    evidence_repo = None
    report_repo = None
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    auth_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    clock = get_clock()
    event_bus = None
    uc = None
    return InProcessSafetyRecovery(uc)


# Use Case Factories
def get_overview_use_case(
    verification_source: Annotated[VerificationSourceAdapter, Depends(get_verification_source)],
    payment_source: Annotated[PaymentSourceAdapter, Depends(get_payment_source)],
    safety_source: Annotated[SafetySourceAdapter, Depends(get_safety_source)],
    notification_source: Annotated[NotificationSourceAdapter, Depends(get_notification_source)],
    messaging_source: Annotated[MessagingSourceAdapter, Depends(get_messaging_source)],
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    audit_repo: Annotated[SqlAlchemyAuditRepository, Depends(get_audit_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    request: Request,
    clock: Annotated[Any, Depends(get_clock)],
) -> GetOverviewUseCase:
    return GetOverviewUseCase(
        verification_source,
        payment_source,
        safety_source,
        notification_source,
        messaging_source,
        issue_repo,
        audit_repo,
        authorizer,
        request.app.state.db_session_factory,
        clock,
        get_settings(),
    )


def get_create_issue_use_case(
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    request: Request,
    clock: Annotated[Any, Depends(get_clock)],
) -> CreateIssueUseCase:
    return CreateIssueUseCase(
        issue_repo,
        authorizer,
        request.app.state.db_session_factory,
        clock,
    )


def get_list_issues_use_case(
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> ListIssuesUseCase:
    return ListIssuesUseCase(issue_repo, authorizer)


def get_get_issue_use_case(
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> GetIssueUseCase:
    return GetIssueUseCase(issue_repo, authorizer)


def get_assign_issue_use_case(
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    request: Request,
    clock: Annotated[Any, Depends(get_clock)],
) -> AssignIssueUseCase:
    return AssignIssueUseCase(
        issue_repo,
        authorizer,
        request.app.state.db_session_factory,
        clock,
    )


def get_change_issue_status_use_case(
    issue_repo: Annotated[SqlAlchemyIssueRepository, Depends(get_issue_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    request: Request,
    clock: Annotated[Any, Depends(get_clock)],
) -> ChangeIssueStatusUseCase:
    return ChangeIssueStatusUseCase(
        issue_repo,
        authorizer,
        request.app.state.db_session_factory,
        clock,
    )


def get_get_account_use_case(
    account_provider: Annotated[InProcessAccountProvider, Depends(get_account_provider)],
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> GetAccountUseCase:
    return GetAccountUseCase(account_provider, staff_role_provider, authorizer)


def get_disable_account_use_case(
    account_provider: Annotated[InProcessAccountProvider, Depends(get_account_provider)],
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> DisableAccountUseCase:
    return DisableAccountUseCase(
        account_provider,
        staff_role_provider,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_reactivate_account_use_case(
    account_provider: Annotated[InProcessAccountProvider, Depends(get_account_provider)],
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> ReactivateAccountUseCase:
    return ReactivateAccountUseCase(
        account_provider,
        staff_role_provider,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_list_staff_use_case(
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> ListStaffUseCase:
    return ListStaffUseCase(staff_role_provider, authorizer)


def get_grant_staff_role_use_case(
    account_provider: Annotated[InProcessAccountProvider, Depends(get_account_provider)],
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> GrantStaffRoleUseCase:
    return GrantStaffRoleUseCase(
        account_provider,
        staff_role_provider,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_revoke_staff_role_use_case(
    account_provider: Annotated[InProcessAccountProvider, Depends(get_account_provider)],
    staff_role_provider: Annotated[InProcessStaffRoleProvider, Depends(get_staff_role_provider)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> AdminRevokeStaffRoleUseCase:
    return AdminRevokeStaffRoleUseCase(
        account_provider,
        staff_role_provider,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_requeue_dead_notification_events_use_case(
    notification_recovery: Annotated[InProcessNotificationRecovery, Depends(get_notification_recovery)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> RequeueDeadNotificationEventsUseCase:
    return RequeueDeadNotificationEventsUseCase(
        notification_recovery,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_requeue_failed_safety_enforcement_use_case(
    safety_recovery: Annotated[InProcessSafetyRecovery, Depends(get_safety_recovery)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
    audit_recorder: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> RequeueFailedSafetyEnforcementUseCase:
    return RequeueFailedSafetyEnforcementUseCase(
        safety_recovery,
        authorizer,
        audit_recorder,
        get_settings(),
    )


def get_list_audit_events_use_case(
    audit_repo: Annotated[SqlAlchemyAuditRepository, Depends(get_audit_repo)],
    authorizer: Annotated[InProcessAuthorizer, Depends(get_authorizer)],
) -> ListAuditEventsUseCase:
    return ListAuditEventsUseCase(audit_repo, authorizer)
