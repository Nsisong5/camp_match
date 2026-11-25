from __future__ import annotations

from typing import Any

class PaystackError(Exception):
    """Base class for Paystack errors."""

class PaystackConnectionError(PaystackError):
    """Network related error."""

class PaystackRejectedError(PaystackError):
    """Provider definitively rejected the request."""

class PaystackUncertainError(PaystackError):
    """Outcome is uncertain (e.g. timeout or unknown status)."""

class PaystackParsingError(PaystackError):
    """Failed to parse response."""
