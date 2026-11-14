"""SMTP email sender adapter using aiosmtplib."""

from __future__ import annotations

import asyncio
from email.message import EmailMessage as StdEmailMessage

import aiosmtplib
import structlog

from camp_match.config.settings import Settings
from camp_match.modules.identity.application.errors import EmailDeliveryError
from camp_match.modules.identity.application.ports.outbound import EmailMessage

logger = structlog.get_logger()


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        if not self._settings.smtp_host or not self._settings.smtp_from_address:
            raise EmailDeliveryError("SMTP host and from address must be configured.")

        msg = StdEmailMessage()
        msg["From"] = self._settings.smtp_from_address
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.text)

        password = (
            self._settings.smtp_password.get_secret_value() if self._settings.smtp_password else ""
        )

        try:

            async def _send() -> None:
                await aiosmtplib.send(
                    msg,
                    hostname=self._settings.smtp_host,
                    port=self._settings.smtp_port,
                    username=self._settings.smtp_username or None,
                    password=password or None,
                    use_tls=False,
                    start_tls=self._settings.smtp_use_starttls,
                    timeout=self._settings.smtp_timeout_seconds,
                )

            await asyncio.wait_for(_send(), timeout=self._settings.smtp_timeout_seconds)
            logger.info("smtp_email_sent", to=message.to, subject=message.subject)
        except TimeoutError as e:
            logger.error("smtp_delivery_timeout", to=message.to)
            raise EmailDeliveryError("SMTP delivery timed out.") from e
        except Exception as e:
            logger.error("smtp_delivery_failed", error=str(e))
            raise EmailDeliveryError(f"SMTP delivery failed: {e}") from e
