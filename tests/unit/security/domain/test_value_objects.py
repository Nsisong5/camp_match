from camp_match.modules.security.domain.policy import _ROLE_PERMISSIONS
from camp_match.modules.security.domain.value_objects import AuthorizationOutcome, Permission, Role


def test_role_permissions_mapping():
    assert Permission.ADMIN_USERS_MANAGE in _ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.VERIFICATION_REVIEW in _ROLE_PERMISSIONS[Role.OPERATIONS]
    assert Permission.VERIFICATION_INSPECT in _ROLE_PERMISSIONS[Role.OPERATIONS]
    assert len(_ROLE_PERMISSIONS[Role.STUDENT]) == 2
    assert Permission.MESSAGING_PARTICIPATE in _ROLE_PERMISSIONS[Role.STUDENT]
    assert Permission.SAFETY_REPORT_SUBMIT in _ROLE_PERMISSIONS[Role.STUDENT]
    assert len(_ROLE_PERMISSIONS[Role.SCOUT]) == 4
    assert Permission.HOUSING_MANAGE in _ROLE_PERMISSIONS[Role.SCOUT]
    assert Permission.VERIFICATION_MANAGE in _ROLE_PERMISSIONS[Role.SCOUT]
    assert Permission.MESSAGING_PARTICIPATE in _ROLE_PERMISSIONS[Role.SCOUT]
    assert Permission.SAFETY_REPORT_SUBMIT in _ROLE_PERMISSIONS[Role.SCOUT]


def test_authorization_outcomes():
    assert AuthorizationOutcome.ALLOWED.name == "ALLOWED"
    assert AuthorizationOutcome.DENIED.name == "DENIED"
    assert AuthorizationOutcome.UNAUTHENTICATED.name == "UNAUTHENTICATED"
    assert AuthorizationOutcome.INVALID_CONTEXT.name == "INVALID_CONTEXT"
