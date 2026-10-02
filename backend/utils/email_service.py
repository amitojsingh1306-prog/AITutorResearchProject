"""Best-effort transactional email sending.

Phase 1 has no production mail infrastructure. This service sends over SMTP
when credentials are configured (see ``Settings.smtp_*``) and otherwise logs
the email it *would* have sent, so local development and CI never fail just
because a mail server isn't configured. A login should never be blocked by
mail delivery, so callers treat a failed send as non-fatal.
"""

import logging
import smtplib
from email.message import EmailMessage

from backend.config import Settings

logger = logging.getLogger(__name__)


class EmailService:
    """Sends transactional emails, falling back to logging when unconfigured."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self._settings.smtp_host
            and self._settings.smtp_username
            and self._settings.smtp_password
        )

    def send_login_confirmation(self, *, name: str, email: str) -> bool:
        """Send a "you just logged in" confirmation email.

        Returns True if the email was handed off to an SMTP server, False if
        it was only logged (no SMTP configured) or delivery failed.
        """

        subject = "You're logged in to ChatbotTutorAI"
        body = (
            f"Hi {name},\n\n"
            "This confirms you just signed in to ChatbotTutorAI.\n"
            "If this wasn't you, you can ignore this email since this is a "
            "local research prototype with no shared account access.\n\n"
            "Happy studying!\n"
            "ChatbotTutorAI"
        )

        if not self.is_configured:
            logger.warning(
                "[EMAIL] SMTP not configured; skipping send. "
                "Would have emailed %s <%s>: %s",
                name,
                email,
                subject,
            )
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._settings.smtp_from_email or self._settings.smtp_username
        message["To"] = email
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=10
            ) as server:
                if self._settings.smtp_use_tls:
                    server.starttls()
                server.login(self._settings.smtp_username, self._settings.smtp_password)
                server.send_message(message)
            return True
        except (smtplib.SMTPException, OSError):
            logger.exception("Failed to send login confirmation email to %s", email)
            return False
