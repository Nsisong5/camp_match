from __future__ import annotations

from camp_match.shared_kernel.application.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class IssueNotFound(NotFoundError):
    code = "issue_not_found"


class AccountNotFound(NotFoundError):
    code = "account_not_found"


class InvalidReason(ValidationError):
    code = "invalid_reason"


class InvalidIssue(ValidationError):
    code = "invalid_issue"


class InvalidResolution(ValidationError):
    code = "invalid_resolution"


class RoleNotManageable(ValidationError):
    code = "role_not_manageable"


class AccountNotActive(ValidationError):
    code = "account_not_active"


class InvalidIssueTransition(ValidationError):
    code = "invalid_issue_transition"


class IssueStateChanged(ConflictError):
    code = "issue_state_changed"


class IdempotencyKeyConflict(ConflictError):
    code = "idempotency_key_conflict"


class SelfActionNotAllowed(ForbiddenError):
    code = "self_action_not_allowed"


class AdminAccountProtected(ForbiddenError):
    code = "admin_account_protected"
