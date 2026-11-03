from __future__ import annotations


class TrustSafetyDomainError(Exception):
    """Base class for Trust & Safety domain errors."""


class InvalidCaseTransition(TrustSafetyDomainError):
    """Raised when an invalid case status transition is attempted."""


class InvalidEnforcementTransition(TrustSafetyDomainError):
    """Raised when an invalid enforcement action transition is attempted."""
