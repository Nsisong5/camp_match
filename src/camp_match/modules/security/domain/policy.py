from __future__ import annotations

from camp_match.modules.security.domain.value_objects import Permission, Role

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset([
        Permission.ADMIN_USERS_MANAGE,
        Permission.UNIVERSITY_MANAGE,
        Permission.HOUSING_MANAGE,
        Permission.VERIFICATION_MANAGE,
        Permission.VERIFICATION_INSPECT,
        Permission.VERIFICATION_REVIEW,
        Permission.BOOKING_CONFIRM,
        Permission.PAYMENT_REVIEW,
        Permission.PAYMENT_AUTHORIZE_RELEASE,
        Permission.PAYMENT_AUTHORIZE_REFUND,
        Permission.SAFETY_ENFORCEMENT_APPROVE,
        Permission.MESSAGING_RESTRICT,
        Permission.HOUSING_SAFETY_SUSPEND,
        Permission.ADMIN_OVERVIEW_VIEW,
        Permission.ADMIN_ISSUES_MANAGE,
        Permission.ADMIN_AUDIT_VIEW,
        Permission.ADMIN_STAFF_MANAGE,
        Permission.ADMIN_RECOVERY_RUN,
        Permission.EXAMPLE_TEST_PERMISSION,
    ]),
    Role.OPERATIONS: frozenset([
        Permission.VERIFICATION_INSPECT,
        Permission.VERIFICATION_REVIEW,
        Permission.BOOKING_CONFIRM,
        Permission.PAYMENT_REVIEW,
        Permission.SAFETY_CASE_REVIEW,
        Permission.SAFETY_EVIDENCE_VIEW,
        Permission.ADMIN_OVERVIEW_VIEW,
        Permission.ADMIN_ISSUES_MANAGE,
    ]),
    Role.STUDENT: frozenset([
        Permission.MESSAGING_PARTICIPATE,
        Permission.SAFETY_REPORT_SUBMIT,
    ]),
    Role.SCOUT: frozenset([
        Permission.HOUSING_MANAGE,
        Permission.VERIFICATION_MANAGE,
        Permission.MESSAGING_PARTICIPATE,
        Permission.SAFETY_REPORT_SUBMIT,
    ]),
}

_OWNERSHIP_SCOPED_PERMISSIONS: frozenset[Permission] = frozenset([
    Permission.EXAMPLE_TEST_PERMISSION,
    Permission.HOUSING_MANAGE,
    Permission.VERIFICATION_MANAGE,
    Permission.VERIFICATION_INSPECT,
])


def permissions_for(role: Role) -> frozenset[Permission]:
    return _ROLE_PERMISSIONS.get(role, frozenset())


def is_ownership_scoped(permission: Permission) -> bool:
    return permission in _OWNERSHIP_SCOPED_PERMISSIONS
