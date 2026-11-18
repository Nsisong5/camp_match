from __future__ import annotations

from camp_match.shared_kernel.application.errors import ApplicationError


class PaymentError(ApplicationError):
    pass


class BookingNotFound(PaymentError):
    pass


class BookingNotEligibleForPayment(PaymentError):
    pass


class UnsupportedProviderCapability(PaymentError):
    pass


class PaymentInitiationError(PaymentError):
    pass


class ReleaseNotEligible(PaymentError):
    def __init__(self, message: str, blocking_reason: str | None = None) -> None:
        super().__init__(message)
        self.blocking_reason = blocking_reason
