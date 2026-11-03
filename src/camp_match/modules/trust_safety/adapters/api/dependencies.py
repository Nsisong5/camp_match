"""Trust & Safety API dependencies."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from camp_match.modules.booking.adapters.api.dependencies import get_get_booking_use_case
from camp_match.modules.booking.application.use_cases.get_booking import GetBookingUseCase
from camp_match.modules.housing.adapters.persistence.repository import (
    SqlAlchemyListingRepository,
    SqlAlchemyPropertyRepository,
)
from camp_match.modules.housing.adapters.security.authorization import (
    InProcessAuthorizationService as HousingAuthService,
)
from camp_match.modules.housing.application.use_cases.unit_listing_management import (
    LiftListingSuspensionUseCase,
    SuspendListingForSafetyUseCase,
)
from camp_match.modules.identity.adapters.persistence.repository import SqlAlchemyIdentityRepository
from camp_match.modules.identity.application.use_cases.disable_account import DisableAccountUseCase
from camp_match.modules.identity.application.use_cases.reactivate_account import ReactivateAccountUseCase
from camp_match.modules.messaging.adapters.api.dependencies import get_participant_guard
from camp_match.modules.messaging.adapters.persistence.repository import SqlAlchemyRestrictionRepository
from camp_match.modules.messaging.adapters.security.authorization import (
    InProcessAuthorizationService as MessagingAuthService,
)
from camp_match.modules.messaging.application.services.participant_guard import ParticipantGuard
from camp_match.modules.messaging.application.use_cases.restriction_management import (
    LiftCommunicationRestrictionUseCase,
    RestrictCommunicationUseCase,
)
from camp_match.modules.profile.adapters.persistence.repository import SqlAlchemyProfileRepository
from camp_match.modules.profile.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from camp_match.modules.security.adapters.persistence.repository import SqlAlchemyRoleRepository
from camp_match.modules.security.adapters.profile.profile_provider import (
    InProcessProfileProvider as SecurityProfileProvider,
)
from camp_match.modules.security.application.use_cases.authorize_action import (
    AuthorizeActionUseCase,
)
from camp_match.modules.trust_safety.adapters.booking.booking_subject_provider import (
    InProcessBookingSubjectProvider,
)
from camp_match.modules.trust_safety.adapters.enforcement.account_enforcer import InProcessAccountEnforcer
from camp_match.modules.trust_safety.adapters.enforcement.communication_enforcer import InProcessCommunicationEnforcer
from camp_match.modules.trust_safety.adapters.enforcement.listing_enforcer import InProcessListingEnforcer
from camp_match.modules.trust_safety.adapters.listing.listing_subject_provider import (
    InProcessListingSubjectProvider,
)
from camp_match.modules.trust_safety.adapters.messaging.message_evidence_provider import (
    InProcessMessageEvidenceProvider,
)
from camp_match.modules.trust_safety.adapters.persistence.case_repository import SqlAlchemyCaseRepository
from camp_match.modules.trust_safety.adapters.persistence.decision_repository import SqlAlchemyDecisionRepository
from camp_match.modules.trust_safety.adapters.persistence.enforcement_repository import SqlAlchemyEnforcementRepository
from camp_match.modules.trust_safety.adapters.persistence.evidence_repository import (
    SqlAlchemyEvidenceRepository,
)
from camp_match.modules.trust_safety.adapters.persistence.note_repository import SqlAlchemyNoteRepository
from camp_match.modules.trust_safety.adapters.persistence.report_repository import (
    SqlAlchemyReportRepository,
)
from camp_match.modules.trust_safety.application.services.case_access import CaseAccess
from camp_match.modules.trust_safety.application.use_cases.add_note import AddNoteUseCase
from camp_match.modules.trust_safety.application.use_cases.approve_enforcement import ApproveEnforcementUseCase
from camp_match.modules.trust_safety.application.use_cases.assign_case import AssignCaseUseCase
from camp_match.modules.trust_safety.application.use_cases.change_case_status import ChangeCaseStatusUseCase
from camp_match.modules.trust_safety.application.use_cases.get_case import GetCaseUseCase
from camp_match.modules.trust_safety.application.use_cases.get_case_history import GetCaseHistoryUseCase
from camp_match.modules.trust_safety.application.use_cases.get_my_report import GetMyReportUseCase
from camp_match.modules.trust_safety.application.use_cases.link_report_to_case import LinkReportToCaseUseCase
from camp_match.modules.trust_safety.application.use_cases.list_cases import ListCasesUseCase
from camp_match.modules.trust_safety.application.use_cases.list_my_reports import ListMyReportsUseCase
from camp_match.modules.trust_safety.application.use_cases.list_review_queue import ListReviewQueueUseCase
from camp_match.modules.trust_safety.application.use_cases.open_case_from_report import OpenCaseFromReportUseCase
from camp_match.modules.trust_safety.application.use_cases.propose_enforcement import ProposeEnforcementUseCase
from camp_match.modules.trust_safety.application.use_cases.record_decision import RecordDecisionUseCase
from camp_match.modules.trust_safety.application.use_cases.reject_enforcement import RejectEnforcementUseCase
from camp_match.modules.trust_safety.application.use_cases.reverse_enforcement import ReverseEnforcementUseCase
from camp_match.modules.trust_safety.application.use_cases.submit_report import SubmitReportUseCase
from camp_match.modules.trust_safety.application.use_cases.triage_case import TriageCaseUseCase
from camp_match.modules.trust_safety.application.use_cases.view_evidence import ViewEvidenceUseCase
from camp_match.platform.clock import get_clock
from camp_match.platform.db.session import get_db_session
from camp_match.platform.db.unit_of_work import SqlAlchemyUnitOfWork
from camp_match.platform.event_bus import get_event_bus
from camp_match.shared_kernel.application.event_bus import EventBus
from camp_match.shared_kernel.application.unit_of_work import UnitOfWork
from camp_match.shared_kernel.domain.clock import Clock


def get_report_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyReportRepository:
    return SqlAlchemyReportRepository(session)


def get_evidence_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyEvidenceRepository:
    return SqlAlchemyEvidenceRepository(session)


def get_case_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyCaseRepository:
    return SqlAlchemyCaseRepository(session)


def get_decision_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyDecisionRepository:
    return SqlAlchemyDecisionRepository(session)


def get_enforcement_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyEnforcementRepository:
    return SqlAlchemyEnforcementRepository(session)


def get_note_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SqlAlchemyNoteRepository:
    return SqlAlchemyNoteRepository(session)


def get_listing_subject_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InProcessListingSubjectProvider:
    listing_repo = SqlAlchemyListingRepository(session)
    property_repo = SqlAlchemyPropertyRepository(session)
    return InProcessListingSubjectProvider(listing_repo, property_repo)


def get_booking_subject_provider(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    get_booking_uc: Annotated[GetBookingUseCase, Depends(get_get_booking_use_case)],
) -> InProcessBookingSubjectProvider:
    property_repo = SqlAlchemyPropertyRepository(session)
    return InProcessBookingSubjectProvider(get_booking_uc, property_repo)


def get_message_evidence_provider(
    guard: Annotated[ParticipantGuard, Depends(get_participant_guard)],
) -> InProcessMessageEvidenceProvider:
    return InProcessMessageEvidenceProvider(guard)


def get_authorization_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Any:
    from camp_match.modules.verification.adapters.security.authorization import (
        InProcessAuthorizationService,
    )
    role_repo = SqlAlchemyRoleRepository(session)
    profile_repo = SqlAlchemyProfileRepository(session)
    profile_use_case = GetCurrentUserProfileUseCase(profile_repo)
    sec_profile_provider = SecurityProfileProvider(profile_use_case)
    authorize_uc = AuthorizeActionUseCase(role_repo, sec_profile_provider)
    return InProcessAuthorizationService(authorize_uc)


def get_case_access(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
) -> CaseAccess:
    return CaseAccess(case_repo, report_repo, auth_service)


def get_uow(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_account_enforcer(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> InProcessAccountEnforcer:
    identity_repo = SqlAlchemyIdentityRepository(session)
    return InProcessAccountEnforcer(
        DisableAccountUseCase(identity_repo, clock, event_bus, uow),
        ReactivateAccountUseCase(identity_repo, clock, event_bus, uow),
    )


def get_listing_enforcer(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> InProcessListingEnforcer:
    listing_repo = SqlAlchemyListingRepository(session)
    auth_service = HousingAuthService(
        AuthorizeActionUseCase(SqlAlchemyRoleRepository(session), SecurityProfileProvider(GetCurrentUserProfileUseCase(SqlAlchemyProfileRepository(session))))
    )
    return InProcessListingEnforcer(
        SuspendListingForSafetyUseCase(listing_repo, auth_service, uow),
        LiftListingSuspensionUseCase(listing_repo, auth_service, uow),
    )


def get_communication_enforcer(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> InProcessCommunicationEnforcer:
    restriction_repo = SqlAlchemyRestrictionRepository(session)
    auth_service = MessagingAuthService(
        AuthorizeActionUseCase(SqlAlchemyRoleRepository(session), SecurityProfileProvider(GetCurrentUserProfileUseCase(SqlAlchemyProfileRepository(session))))
    )
    return InProcessCommunicationEnforcer(
        RestrictCommunicationUseCase(restriction_repo, auth_service, uow),
        LiftCommunicationRestrictionUseCase(restriction_repo, auth_service, uow),
    )


def get_submit_report_use_case(
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    listing_provider: Annotated[InProcessListingSubjectProvider, Depends(get_listing_subject_provider)],
    booking_provider: Annotated[InProcessBookingSubjectProvider, Depends(get_booking_subject_provider)],
    message_provider: Annotated[InProcessMessageEvidenceProvider, Depends(get_message_evidence_provider)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> SubmitReportUseCase:
    return SubmitReportUseCase(
        report_repo=report_repo,
        evidence_repo=evidence_repo,
        listing_subject_provider=listing_provider,
        booking_subject_provider=booking_provider,
        message_evidence_provider=message_provider,
        authorization_service=auth_service,
        event_bus=event_bus,
        unit_of_work=uow,
        clock=clock,
    )


def get_list_my_reports_use_case(
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
) -> ListMyReportsUseCase:
    return ListMyReportsUseCase(report_repo)


def get_get_my_report_use_case(
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
) -> GetMyReportUseCase:
    return GetMyReportUseCase(report_repo)


def get_list_review_queue_use_case(
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
) -> ListReviewQueueUseCase:
    return ListReviewQueueUseCase(report_repo, auth_service)


def get_open_case_from_report_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    note_repo: Annotated[SqlAlchemyNoteRepository, Depends(get_note_repository)],
    decision_repo: Annotated[SqlAlchemyDecisionRepository, Depends(get_decision_repository)],
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> OpenCaseFromReportUseCase:
    return OpenCaseFromReportUseCase(
        case_repo=case_repo,
        report_repo=report_repo,
        evidence_repo=evidence_repo,
        note_repo=note_repo,
        decision_repo=decision_repo,
        enforcement_repo=enforcement_repo,
        authorization_service=auth_service,
        unit_of_work=uow,
        clock=clock,
    )


def get_link_report_to_case_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> LinkReportToCaseUseCase:
    return LinkReportToCaseUseCase(case_repo, report_repo, case_access, uow, clock)


def get_list_cases_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
) -> ListCasesUseCase:
    return ListCasesUseCase(case_repo, auth_service)


def get_get_case_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    note_repo: Annotated[SqlAlchemyNoteRepository, Depends(get_note_repository)],
    decision_repo: Annotated[SqlAlchemyDecisionRepository, Depends(get_decision_repository)],
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
) -> GetCaseUseCase:
    return GetCaseUseCase(
        case_repo, report_repo, evidence_repo, note_repo, decision_repo, enforcement_repo, case_access, auth_service
    )


def get_triage_case_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> TriageCaseUseCase:
    return TriageCaseUseCase(case_repo, case_access, uow, clock)


def get_assign_case_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AssignCaseUseCase:
    return AssignCaseUseCase(case_repo, case_access, auth_service, uow, clock)


def get_change_case_status_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    decision_repo: Annotated[SqlAlchemyDecisionRepository, Depends(get_decision_repository)],
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ChangeCaseStatusUseCase:
    return ChangeCaseStatusUseCase(
        case_repo, report_repo, decision_repo, enforcement_repo, case_access, auth_service, event_bus, uow, clock
    )


def get_view_evidence_use_case(
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    auth_service: Annotated[Any, Depends(get_authorization_service)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ViewEvidenceUseCase:
    return ViewEvidenceUseCase(evidence_repo, case_repo, report_repo, case_access, auth_service, uow, clock)


def get_add_note_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    note_repo: Annotated[SqlAlchemyNoteRepository, Depends(get_note_repository)],
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AddNoteUseCase:
    return AddNoteUseCase(case_repo, note_repo, evidence_repo, case_access, uow, clock)


def get_get_case_history_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
) -> GetCaseHistoryUseCase:
    return GetCaseHistoryUseCase(case_repo, case_access)


def get_record_decision_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    decision_repo: Annotated[SqlAlchemyDecisionRepository, Depends(get_decision_repository)],
    evidence_repo: Annotated[SqlAlchemyEvidenceRepository, Depends(get_evidence_repository)],
    note_repo: Annotated[SqlAlchemyNoteRepository, Depends(get_note_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RecordDecisionUseCase:
    return RecordDecisionUseCase(case_repo, decision_repo, evidence_repo, note_repo, case_access, uow, clock)


def get_propose_enforcement_use_case(
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    decision_repo: Annotated[SqlAlchemyDecisionRepository, Depends(get_decision_repository)],
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    report_repo: Annotated[SqlAlchemyReportRepository, Depends(get_report_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProposeEnforcementUseCase:
    return ProposeEnforcementUseCase(
        case_repo=case_repo,
        decision_repo=decision_repo,
        enforcement_repo=enforcement_repo,
        report_repo=report_repo,
        case_access=case_access,
        event_bus=event_bus,
        unit_of_work=uow,
        clock=clock,
    )


def get_approve_enforcement_use_case(
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    account_enforcer: Annotated[InProcessAccountEnforcer, Depends(get_account_enforcer)],
    listing_enforcer: Annotated[InProcessListingEnforcer, Depends(get_listing_enforcer)],
    communication_enforcer: Annotated[InProcessCommunicationEnforcer, Depends(get_communication_enforcer)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApproveEnforcementUseCase:
    return ApproveEnforcementUseCase(
        enforcement_repo=enforcement_repo,
        case_repo=case_repo,
        case_access=case_access,
        account_enforcer=account_enforcer,
        listing_enforcer=listing_enforcer,
        communication_enforcer=communication_enforcer,
        event_bus=event_bus,
        unit_of_work=uow,
        clock=clock,
    )


def get_reject_enforcement_use_case(
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> RejectEnforcementUseCase:
    return RejectEnforcementUseCase(
        enforcement_repo=enforcement_repo,
        case_repo=case_repo,
        case_access=case_access,
        unit_of_work=uow,
    )


def get_reverse_enforcement_use_case(
    enforcement_repo: Annotated[SqlAlchemyEnforcementRepository, Depends(get_enforcement_repository)],
    case_repo: Annotated[SqlAlchemyCaseRepository, Depends(get_case_repository)],
    case_access: Annotated[CaseAccess, Depends(get_case_access)],
    account_enforcer: Annotated[InProcessAccountEnforcer, Depends(get_account_enforcer)],
    listing_enforcer: Annotated[InProcessListingEnforcer, Depends(get_listing_enforcer)],
    communication_enforcer: Annotated[InProcessCommunicationEnforcer, Depends(get_communication_enforcer)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ReverseEnforcementUseCase:
    return ReverseEnforcementUseCase(
        enforcement_repo=enforcement_repo,
        case_repo=case_repo,
        case_access=case_access,
        account_enforcer=account_enforcer,
        listing_enforcer=listing_enforcer,
        communication_enforcer=communication_enforcer,
        event_bus=event_bus,
        unit_of_work=uow,
        clock=clock,
    )
