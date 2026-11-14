from __future__ import annotations

from camp_match.shared_kernel.domain.errors import DomainError


class PlatformError(DomainError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class UnknownEventType(PlatformError):
    def __init__(self, event_type: str) -> None:
        super().__init__(f"Unknown event type: {event_type}", code="UNKNOWN_EVENT_TYPE")
        self.event_type = event_type


class InvalidEventPayload(PlatformError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="INVALID_EVENT_PAYLOAD")
