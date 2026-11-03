from __future__ import annotations

from camp_match.shared_kernel.application.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)


class ConversationNotFound(NotFoundError):
    code = "conversation_not_found"


class RestrictionNotFound(NotFoundError):
    code = "restriction_not_found"


class ConversationContextNotFound(NotFoundError):
    code = "conversation_context_not_found"


class SelfConversationNotAllowed(ForbiddenError):
    code = "self_conversation_not_allowed"


class CommunicationRestricted(ForbiddenError):
    code = "communication_restricted"


class ConversationContextUnavailable(ValidationError):
    code = "conversation_context_unavailable"


class InvalidMessageContent(ValidationError):
    code = "invalid_message_content"


class InvalidClientMessageId(ValidationError):
    code = "invalid_client_message_id"


class InvalidHistoryCursor(ValidationError):
    code = "invalid_history_cursor"


class InvalidReadPosition(ValidationError):
    code = "invalid_read_position"


class ClientMessageIdConflict(ConflictError):
    code = "client_message_id_conflict"


class RateLimitExceeded(RateLimitedError):
    code = "rate_limit_exceeded"


class DuplicateClientMessageId(Exception):
    """Internal signal when client_message_id uniqueness is violated."""
