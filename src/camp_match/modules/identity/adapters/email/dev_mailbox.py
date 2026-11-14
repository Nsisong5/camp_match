"""In-memory dev mailbox storage buffer."""

from __future__ import annotations

from camp_match.modules.identity.application.ports.outbound import EmailMessage


class DevMailbox:
    def __init__(self, max_size: int = 50) -> None:
        self._max_size = max_size
        self._messages: list[EmailMessage] = []

    def add(self, message: EmailMessage) -> None:
        self._messages.append(message)
        if len(self._messages) > self._max_size:
            self._messages.pop(0)

    def list_for_address(self, email: str) -> list[EmailMessage]:
        normalized = email.strip().lower()
        matched = [m for m in self._messages if m.to.strip().lower() == normalized]
        # Newest first, at most 10
        return list(reversed(matched))[:10]

    def clear(self) -> None:
        self._messages.clear()
