from __future__ import annotations

import pytest
from camp_match.modules.security.domain.policy import is_ownership_scoped, permissions_for
from camp_match.modules.security.domain.value_objects import Permission, Role


def test_permissions_for_role():
    assert Permission.ADMIN_USERS_MANAGE in permissions_for(Role.ADMIN)
    assert Permission.UNIVERSITY_MANAGE in permissions_for(Role.ADMIN)
    assert Permission.HOUSING_MANAGE in permissions_for(Role.ADMIN)
    assert Permission.VERIFICATION_REVIEW in permissions_for(Role.OPERATIONS)
    assert Permission.VERIFICATION_INSPECT in permissions_for(Role.OPERATIONS)
    assert Permission.HOUSING_MANAGE in permissions_for(Role.SCOUT)

    # Messaging participate checks
    assert Permission.MESSAGING_PARTICIPATE in permissions_for(Role.STUDENT)
    assert Permission.MESSAGING_PARTICIPATE in permissions_for(Role.SCOUT)
    assert Permission.MESSAGING_PARTICIPATE not in permissions_for(Role.ADMIN)
    assert Permission.MESSAGING_PARTICIPATE not in permissions_for(Role.OPERATIONS)


@pytest.mark.parametrize(
    "permission,expected_roles",
    [
        (Permission.SAFETY_REPORT_SUBMIT, {Role.STUDENT, Role.SCOUT}),
        (Permission.SAFETY_CASE_REVIEW, {Role.OPERATIONS}),
        (Permission.SAFETY_EVIDENCE_VIEW, {Role.OPERATIONS}),
        (Permission.SAFETY_ENFORCEMENT_APPROVE, {Role.ADMIN}),
        (Permission.MESSAGING_RESTRICT, {Role.ADMIN}),
        (Permission.HOUSING_SAFETY_SUSPEND, {Role.ADMIN}),
    ],
)
def test_trust_safety_permissions_assignment(permission, expected_roles):
    all_roles = {Role.ADMIN, Role.OPERATIONS, Role.STUDENT, Role.SCOUT}
    for role in all_roles:
        if role in expected_roles:
            assert permission in permissions_for(role)
        else:
            assert permission not in permissions_for(role)
    assert not is_ownership_scoped(permission)


@pytest.mark.parametrize(
    "permission,expected_roles",
    [
        (Permission.ADMIN_OVERVIEW_VIEW, {Role.ADMIN, Role.OPERATIONS}),
        (Permission.ADMIN_ISSUES_MANAGE, {Role.ADMIN, Role.OPERATIONS}),
        (Permission.ADMIN_AUDIT_VIEW, {Role.ADMIN}),
        (Permission.ADMIN_STAFF_MANAGE, {Role.ADMIN}),
        (Permission.ADMIN_RECOVERY_RUN, {Role.ADMIN}),
    ],
)
def test_admin_permissions_assignment(permission, expected_roles):
    all_roles = {Role.ADMIN, Role.OPERATIONS, Role.STUDENT, Role.SCOUT}
    for role in all_roles:
        if role in expected_roles:
            assert permission in permissions_for(role)
        else:
            assert permission not in permissions_for(role)
    assert not is_ownership_scoped(permission)


def test_is_ownership_scoped():
    assert not is_ownership_scoped(Permission.ADMIN_USERS_MANAGE)
    assert is_ownership_scoped(Permission.EXAMPLE_TEST_PERMISSION)
    assert is_ownership_scoped(Permission.HOUSING_MANAGE)
    assert not is_ownership_scoped(Permission.MESSAGING_PARTICIPATE)
    assert not is_ownership_scoped(Permission.SAFETY_REPORT_SUBMIT)
    assert not is_ownership_scoped(Permission.SAFETY_CASE_REVIEW)
    assert not is_ownership_scoped(Permission.SAFETY_EVIDENCE_VIEW)
    assert not is_ownership_scoped(Permission.SAFETY_ENFORCEMENT_APPROVE)
    assert not is_ownership_scoped(Permission.MESSAGING_RESTRICT)
    assert not is_ownership_scoped(Permission.HOUSING_SAFETY_SUSPEND)
    assert not is_ownership_scoped(Permission.ADMIN_OVERVIEW_VIEW)
    assert not is_ownership_scoped(Permission.ADMIN_ISSUES_MANAGE)
    assert not is_ownership_scoped(Permission.ADMIN_AUDIT_VIEW)
    assert not is_ownership_scoped(Permission.ADMIN_STAFF_MANAGE)
    assert not is_ownership_scoped(Permission.ADMIN_RECOVERY_RUN)
