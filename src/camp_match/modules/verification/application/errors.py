from camp_match.shared_kernel.application.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class VerificationCaseNotFound(NotFoundError):
    def __init__(self, message: str = "Verification case not found.") -> None:
        super().__init__(message=message)
        self.code = "verification_case_not_found"


class EvidenceNotFound(NotFoundError):
    def __init__(self, message: str = "Evidence not found.") -> None:
        super().__init__(message=message)
        self.code = "evidence_not_found"


class InspectionNotFound(NotFoundError):
    def __init__(self, message: str = "Inspection not found.") -> None:
        super().__init__(message=message)
        self.code = "inspection_not_found"


class InvalidVerificationTransition(ValidationError):
    def __init__(self, message: str = "Invalid verification transition.") -> None:
        super().__init__(message=message)
        self.code = "invalid_verification_transition"


class EvidenceRequirementNotSatisfied(ValidationError):
    def __init__(self, message: str = "Evidence requirement not satisfied.") -> None:
        super().__init__(message=message)
        self.code = "evidence_requirement_not_satisfied"


class DecisionNotAllowed(ValidationError):
    def __init__(self, message: str = "Decision not allowed.") -> None:
        super().__init__(message=message)
        self.code = "decision_not_allowed"


class VerificationForbiddenError(ForbiddenError):
    def __init__(self, message: str = "Forbidden operation.") -> None:
        super().__init__(message=message)
        self.code = "forbidden"
