from __future__ import annotations

from camp_match.shared_kernel.application.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class BookingNotFound(NotFoundError):
    def __init__(self, message: str = "Booking not found.") -> None:
        super().__init__(message=message)
        self.code = "booking_not_found"


class ListingNotBookable(ValidationError):
    def __init__(self, message: str = "Listing is not bookable.") -> None:
        super().__init__(message=message)
        self.code = "listing_not_bookable"


class SelfBookingNotAllowed(ForbiddenError):
    def __init__(self, message: str = "Cannot book your own property.") -> None:
        super().__init__(message=message)
        self.code = "self_booking_not_allowed"


class VerificationRequirementNotSatisfied(ValidationError):
    def __init__(self, message: str = "Property verification requirement not satisfied.") -> None:
        super().__init__(message=message)
        self.code = "verification_requirement_not_satisfied"


class InventoryUnavailable(ValidationError):
    def __init__(self, message: str = "Inventory unavailable.") -> None:
        super().__init__(message=message)
        self.code = "inventory_unavailable"


class InvalidBookingStateTransition(ValidationError):
    def __init__(self, message: str = "Invalid booking state transition.") -> None:
        super().__init__(message=message)
        self.code = "invalid_booking_state_transition"
