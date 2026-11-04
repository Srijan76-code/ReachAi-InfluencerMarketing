"""Sending email (spec §0: the only emails ReachAI sends are share-link codes, for now).

Gmail SMTP from the team account until there's a domain; then this file switches to Resend.
Credentials come from env vars only (rule 8) and are never logged. Without them, email is off and
callers must check `email_enabled()` first.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # implicit TLS
SMTP_TIMEOUT_SECONDS = 15
FROM_NAME = "ReachAI"


class EmailNotConfigured(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    return os.getenv("GMAIL_SMTP_USER", "").strip(), os.getenv("GMAIL_SMTP_APP_PASSWORD", "").replace(" ", "")


def email_enabled() -> bool:
    user, password = _credentials()
    return bool(user and password)


def _send_sync(to: str, subject: str, text: str) -> None:
    user, password = _credentials()
    msg = EmailMessage()
    msg["From"] = formataddr((FROM_NAME, user))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=SMTP_TIMEOUT_SECONDS) as s:
        s.login(user, password)
        s.send_message(msg)


async def send_email(to: str, subject: str, text: str) -> None:
    """Plain-text email (best deliverability for codes). Raises EmailSendError; never logs secrets."""
    if not email_enabled():
        raise EmailNotConfigured("email isn't set up")
    try:
        await asyncio.to_thread(_send_sync, to, subject, text)
    except Exception as exc:  # smtplib errors can include server text, never our password
        logger.warning("email to %s failed: %s", to.split("@")[-1], type(exc).__name__)
        raise EmailSendError("couldn't send the email") from exc
