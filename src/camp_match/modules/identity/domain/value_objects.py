"""Identity module domain value objects and enums."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, StrEnum, auto


@dataclass(frozen=True)
class EmailAddress:
    """Wraps and normalizes a single email string."""

    value: str

    def __init__(self, value: str) -> None:
        normalized = value.strip().lower()
        if len(normalized) > 254:
            raise ValueError("Email address too long")

        # basic valid shape: local-part@domain, domain contains at least one dot
        if not re.match(r"[^@]+@[^@]+\.[^@]+", normalized):
            raise ValueError("Invalid email address format")

        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


class AccountStatus(Enum):
    """Possible states for a UserAccount."""

    ACTIVE = auto()
    SUSPENDED = auto()
    DISABLED = auto()


class EmailVerificationSource(StrEnum):
    """Source by which an email address was verified."""

    OTP = "OTP"
    GOOGLE = "GOOGLE"
    LEGACY = "LEGACY"


class SignInMethod(StrEnum):
    """Available sign-in methods for an account."""

    PASSWORD = "PASSWORD"
    GOOGLE = "GOOGLE"


class OneTimeCodePurpose(StrEnum):
    """Purpose of a one-time code."""

    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"


class ExternalProvider(StrEnum):
    """External identity providers."""

    GOOGLE = "GOOGLE"
