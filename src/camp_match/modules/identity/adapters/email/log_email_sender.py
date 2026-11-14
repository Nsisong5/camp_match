"""Log email sender adapter for local/test environments."""

from __future__ import annotations

import structlog

from camp_match.config.settings import Settings
from camp_match.modules.identity.adapters.email.dev_mailbox import DevMailbox
from camp_match.modules.identity.application.ports.outbound import EmailMessage

logger = structlog.get_logger()


class LogEmailSender:
    def __init__(self, mailbox: DevMailbox, settings: Settings) -> None:
        env = settings.app_env.lower()
        if env not in ("local", "test"):
            raise ValueError("LogEmailSender is only allowed in local or test environments.")
        self._mailbox = mailbox

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email_sent_to_log_sender",
            to=message.to,
            subject=message.subject,
        )
        self._mailbox.add(message)
