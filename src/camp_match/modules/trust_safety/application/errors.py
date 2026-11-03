"""Trust & Safety application errors."""
from __future__ import annotations

from camp_match.shared_kernel.application.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from camp_match.shared_kernel.domain.identifiers import EntityId


class ReportNotFound(NotFoundError):
    code = "report_not_found"


class CaseNotFound(NotFoundError):
    code = "case_not_found"


class EvidenceNotFound(NotFoundError):
    code = "evidence_not_found"


class EnforcementActionNotFound(NotFoundError):
    code = "enforcement_action_not_found"


class InvalidReportSubject(ValidationError):
    code = "invalid_report_subject"


class InvalidReportDescription(ValidationError):
    code = "invalid_report_description"


class InvalidIdempotencyKey(ValidationError):
    code = "invalid_idempotency_key"


class TransitionRequirementNotMet(ValidationError):
    code = "transition_requirement_not_met"


class InvalidNote(ValidationError):
    code = "invalid_note"


class InvalidDecision(ValidationError):
    code = "invalid_decision"


class InvalidEnforcementRequest(ValidationError):
    code = "invalid_enforcement_request"


class DuplicateOpenReport(ConflictError):
    code = "duplicate_open_report"

    def __init__(
        self,
        existing_report_id: EntityId,
        message: str = "Duplicate open report exists.",
    ) -> None:
        super().__init__(message)
        self.existing_report_id = existing_report_id


class IdempotencyKeyConflict(ConflictError):
    code = "idempotency_key_conflict"


class InvalidCaseTransition(ConflictError):
    code = "invalid_case_transition"


class CaseStateChanged(ConflictError):
    code = "case_state_changed"


class ReportAlreadyLinked(ConflictError):
    code = "report_already_linked"


class DuplicateEnforcementAction(ConflictError):
    code = "duplicate_enforcement_action"


class InvalidEnforcementTransition(ConflictError):
    code = "invalid_enforcement_transition"


class SeparationOfDutiesViolation(ForbiddenError):
    code = "separation_of_duties_violation"


class ReportRateLimitExceeded(RateLimitedError):
    code = "rate_limit_exceeded"


class TransientEnforcementError(Exception):
    """Internal exception for transient enforcement failures (retryable)."""


class PermanentEnforcementError(Exception):
    """Internal exception for permanent enforcement failures (non-retryable)."""
