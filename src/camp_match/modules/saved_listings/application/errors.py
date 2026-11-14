"""Saved listings application errors."""

from camp_match.shared_kernel.application.errors import ConflictError, NotFoundError


class ListingNotSavable(NotFoundError):
    code = "listing_not_found"


class CannotSaveOwnListing(ConflictError):
    code = "cannot_save_own_listing"


class SavedLimitReached(ConflictError):
    code = "saved_limit_reached"
