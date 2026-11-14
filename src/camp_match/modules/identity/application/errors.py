"""Application-level errors for the Identity module."""

from camp_match.shared_kernel.application.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class IdentityAlreadyExists(ConflictError):
    """Email is already registered to an account."""

    code = "identity_already_exists"


class InvalidCredentials(UnauthorizedError):
    """Email/password combination didn't check out or token is invalid."""

    code = "invalid_credentials"


class AccountSuspended(ForbiddenError):
    """Credentials were valid; the account's status forbids login right now."""

    code = "account_suspended"


class AccountDisabled(ForbiddenError):
    """Credentials were valid; the account's status forbids login right now."""

    code = "account_disabled"


class IdentityNotFound(NotFoundError):
    """Looked up by ID and nothing's there."""

    code = "identity_not_found"


class InvalidAuthenticationRequest(ValidationError):
    """Reserved for a business-level input problem Pydantic couldn't have caught."""

    code = "invalid_authentication_request"


class EmailNotVerified(ForbiddenError):
    """Your email address has not been verified."""

    code = "email_not_verified"

    def __init__(self, message: str = "Your email address has not been verified.") -> None:
        super().__init__(message)


class InvalidOrExpiredCode(ValidationError):
    """That code is invalid or has expired."""

    code = "invalid_or_expired_code"

    def __init__(self, message: str = "That code is invalid or has expired.") -> None:
        super().__init__(message)


class InvalidGoogleToken(UnauthorizedError):
    """Google sign-in could not be verified."""

    code = "invalid_google_token"

    def __init__(self, message: str = "Google sign-in could not be verified.") -> None:
        super().__init__(message)


class GoogleEmailNotSupported(ValidationError):
    """This Google account's email can't be used to sign up."""

    code = "google_email_not_supported"

    def __init__(
        self,
        message: str = (
            "This Google account's email can't be used to sign up. "
            "Please register with your email and a password."
        ),
    ) -> None:
        super().__init__(message)


class AccountExistsUseExistingMethod(ConflictError):
    """An account with this email already exists."""

    code = "account_exists"

    def __init__(
        self,
        message: str = (
            "An account with this email already exists. "
            "Sign in the way you did before, then link Google from your account settings."
        ),
    ) -> None:
        super().__init__(message)


class GoogleAlreadyLinked(ConflictError):
    """A Google account is already linked."""

    code = "google_already_linked"

    def __init__(self, message: str = "A Google account is already linked.") -> None:
        super().__init__(message)


class GoogleIdentityInUse(ConflictError):
    """That Google account is linked to a different account."""

    code = "google_identity_in_use"

    def __init__(
        self, message: str = "That Google account is linked to a different account."
    ) -> None:
        super().__init__(message)


class LastSignInMethod(ConflictError):
    """You need at least one way to sign in."""

    code = "last_sign_in_method"

    def __init__(
        self,
        message: str = "You need at least one way to sign in. Set a password first.",
    ) -> None:
        super().__init__(message)


class PasswordAlreadySet(ConflictError):
    """This account already has a password."""

    code = "password_already_set"

    def __init__(self, message: str = "This account already has a password.") -> None:
        super().__init__(message)


class GoogleSignInDisabled(NotFoundError):
    """Google sign-in is not available."""

    code = "google_sign_in_disabled"

    def __init__(self, message: str = "Google sign-in is not available.") -> None:
        super().__init__(message)


class EmailDeliveryError(Exception):
    """Plain infrastructure error when email delivery fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
