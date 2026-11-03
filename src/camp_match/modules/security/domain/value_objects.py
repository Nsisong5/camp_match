from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from camp_match.shared_kernel.domain.identifiers import EntityId


class Role(Enum):
    STUDENT = auto()
    SCOUT = auto()
    ADMIN = auto()
    OPERATIONS = auto()


class Permission(Enum):
    ADMIN_USERS_MANAGE = "admin.users.manage"
    UNIVERSITY_MANAGE = "university.manage"
    HOUSING_MANAGE = "housing.manage"
    VERIFICATION_MANAGE = "verification.manage"
    VERIFICATION_INSPECT = "verification.inspect"
    VERIFICATION_REVIEW = "verification.review"
    BOOKING_CONFIRM = "booking.confirm"
    PAYMENT_REVIEW = "payment.review"
    PAYMENT_AUTHORIZE_RELEASE = "payment.authorize_release"
    PAYMENT_AUTHORIZE_REFUND = "payment.authorize_refund"
    MESSAGING_PARTICIPATE = "messaging.participate"
    SAFETY_REPORT_SUBMIT = "safety.report.submit"
    SAFETY_CASE_REVIEW = "safety.case.review"
    SAFETY_EVIDENCE_VIEW = "safety.evidence.view"
    SAFETY_ENFORCEMENT_APPROVE = "safety.enforcement.approve"
    MESSAGING_RESTRICT = "messaging.restrict"
    HOUSING_SAFETY_SUSPEND = "housing.safety.suspend"
    ADMIN_OVERVIEW_VIEW = "admin.overview.view"
    ADMIN_ISSUES_MANAGE = "admin.issues.manage"
    ADMIN_AUDIT_VIEW = "admin.audit.view"
    ADMIN_STAFF_MANAGE = "admin.staff.manage"
    ADMIN_RECOVERY_RUN = "admin.recovery.run"
    EXAMPLE_TEST_PERMISSION = "test.ownership.scoped"  # Test-only


class AuthorizationOutcome(Enum):
    ALLOWED = auto()
    DENIED = auto()
    UNAUTHENTICATED = auto()
    INVALID_CONTEXT = auto()


@dataclass(frozen=True)
class AuthorizationDecision:
    outcome: AuthorizationOutcome
    reason: str


@dataclass(frozen=True)
class Principal:
    identity_id: EntityId
    roles: frozenset[Role]

    @classmethod
    def create(cls, identity_id: EntityId, roles: frozenset[Role]) -> Principal:
        return cls(identity_id=identity_id, roles=roles)
