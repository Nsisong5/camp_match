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
