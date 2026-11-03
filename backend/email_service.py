"""Sending the emails the account flows need: verification, password reset, invitations.

EMAIL_BACKEND   log (default): messages are only written to the log, for development
                smtp: sent through your SMTP server
APP_URL         the frontend's public address, used to build the links in the emails
EMAIL_FROM      the From address
SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_STARTTLS (true)

The log backend prints links that sign people in or reset passwords. Never use it where logs
are shared.
"""
import asyncio
import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import List, Tuple

logger = logging.getLogger(__name__)


def app_url() -> str:
    return os.getenv("APP_URL", "http://localhost:3000").rstrip("/")


class EmailSender(ABC):
    name = "base"

    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> None: ...


class LogEmailSender(EmailSender):
    name = "log"

    def __init__(self):
        self.outbox: List[Tuple[str, str, str]] = []  # (to, subject, body), for tests and local use

    async def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        logger.info(f"EMAIL (not sent, EMAIL_BACKEND=log) to={to} subject={subject!r}\n{body}")


class SmtpEmailSender(EmailSender):
    name = "smtp"

    def __init__(self):
        self.host = os.environ["SMTP_HOST"]
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.starttls = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
        self.sender = os.getenv("EMAIL_FROM", self.user or "no-reply@localhost")

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            if self.starttls:
                server.starttls()
            if self.user:
                server.login(self.user, self.password)
            server.send_message(message)

    async def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, to, subject
        message.set_content(body)
        await asyncio.to_thread(self._deliver, message)


def get_email_sender() -> EmailSender:
    backend = os.getenv("EMAIL_BACKEND", "log").lower()
    if backend == "smtp":
        return SmtpEmailSender()
    if backend != "log":
        raise ValueError("EMAIL_BACKEND must be 'log' or 'smtp'.")
    return LogEmailSender()


async def send_quietly(sender: EmailSender, to: str, subject: str, body: str) -> bool:
    """Send an email; a delivery failure is logged and reported, never raised.
    Callers must not reveal it to the user, or it would confirm whether an address has an account."""
    try:
        await sender.send(to, subject, body)
        return True
    except Exception as e:
        logger.error(f"Could not send email '{subject}': {e}")
        return False


def verification_email(name: str, token: str) -> Tuple[str, str]:
    return "Confirm your email address", (
        f"Hi {name},\n\nConfirm your email address to finish setting up your account:\n\n"
        f"{app_url()}/verify-email?token={token}\n\nThe link works for 24 hours. "
        "If you did not create an account, ignore this message."
    )


def password_reset_email(name: str, token: str) -> Tuple[str, str]:
    return "Reset your password", (
        f"Hi {name},\n\nUse this link to choose a new password:\n\n"
        f"{app_url()}/reset-password?token={token}\n\nThe link works for 1 hour and only once. "
        "If you did not ask for this, ignore this message: your password has not changed."
    )


def invitation_email(inviter: str, organization: str, role: str, token: str) -> Tuple[str, str]:
    return f"{inviter} invited you to {organization}", (
        f"{inviter} invited you to join {organization} as {role}.\n\n"
        f"Accept the invitation:\n\n{app_url()}/accept-invite?token={token}\n\n"
        "The invitation is valid for 7 days. If you were not expecting it, ignore this message."
    )
